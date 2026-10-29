"""Supporting documents: signed upload -> quarantine -> scan -> CLEAN or REJECTED.

The scan reuses ``app.uploads.inspect_upload`` (type allowlist, magic bytes, size, PDF active content).
A rejected object is deleted; its metadata and reason stay for the audit trail.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from sqlalchemy import Engine, insert, select, update

from app.uploads import UploadRejected, inspect_upload, safe_filename
from policyguard.infra import tables as t
from policyguard.infra.pg import append_audit, new_id
from policyguard.infra.storage import ObjectStore, sign, verify

from .errors import Forbidden, NotFound, ValidationFailed
from .service import Actor

ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".txt")


class PayloadTooLarge(ValidationFailed):
    status, code = 413, "payload_too_large"


class UploadService:
    def __init__(self, engine: Engine, store: ObjectStore, clock, secret: bytes, max_bytes: int, ttl_s: int):
        self.engine, self.store, self.clock = engine, store, clock
        self.secret, self.max_bytes, self.ttl_s = secret, max_bytes, ttl_s

    def create(self, actor: Actor, filename: str, content_type: str, size: int) -> dict:
        if "payer" not in actor.roles and "reviewer" not in actor.roles:
            raise Forbidden("Your role cannot upload documents.")
        name = safe_filename(filename)
        if not name.lower().endswith(ALLOWED_EXTENSIONS):
            raise ValidationFailed("Upload a PDF, PNG, JPG or TXT file.", "filename")
        if size <= 0 or size > self.max_bytes:
            raise ValidationFailed(f"Files can be up to {self.max_bytes // 1_000_000} MB.", "size")
        now = self.clock()
        upload_id = new_id("upl")
        expires = now + timedelta(seconds=self.ttl_s)
        with self.engine.begin() as conn:
            conn.execute(insert(t.uploads).values(
                upload_id=upload_id, tenant_id=actor.tenant_id, created_by=actor.user_id,
                object_key=f"quarantine/{actor.tenant_id}/{upload_id}", filename=name, content_type=content_type[:100],
                declared_size=size, status="PENDING", expires_at=expires, created_at=now))
        exp = int(expires.timestamp())
        return {"upload_id": upload_id, "expires_at": expires.isoformat(), "max_bytes": size,
                "upload_url": f"/v1/uploads/{upload_id}/blob?exp={exp}&sig={sign(self.secret, upload_id, exp)}"}

    def put_blob(self, upload_id: str, exp: int, sig: str, data: bytes) -> None:
        if not verify(self.secret, upload_id, exp, sig, int(self.clock().timestamp())):
            raise Forbidden("The upload link is invalid or has expired.")
        with self.engine.begin() as conn:
            row = conn.execute(select(t.uploads).where(t.uploads.c.upload_id == upload_id).with_for_update()).first()
            if row is None or row.status != "PENDING":
                raise Forbidden("The upload link was already used.")
            if len(data) > row.declared_size or len(data) > self.max_bytes:
                raise PayloadTooLarge("The file is larger than announced.", "file")
            self.store.put(row.object_key, data)
            conn.execute(update(t.uploads).where(t.uploads.c.upload_id == upload_id).values(
                status="QUARANTINED", size=len(data), sha256=hashlib.sha256(data).hexdigest()))

    def complete(self, actor: Actor, upload_id: str) -> dict:
        now = self.clock()
        with self.engine.begin() as conn:
            row = conn.execute(select(t.uploads).where(t.uploads.c.upload_id == upload_id,
                                                       t.uploads.c.tenant_id == actor.tenant_id).with_for_update()).first()
            if row is None or (row.created_by != actor.user_id and "reviewer" not in actor.roles):
                raise NotFound("Upload not found.")
            if row.status in ("CLEAN", "REJECTED"):
                return self._view(row)
            if row.status != "QUARANTINED":
                raise ValidationFailed("Upload the file before completing it.", "upload")
            data = self.store.get(row.object_key)
            try:
                inspect_upload(row.filename, data, self.max_bytes)
                clean_key = f"clean/{row.tenant_id}/{upload_id}"
                self.store.move(row.object_key, clean_key)
                values = {"status": "CLEAN", "object_key": clean_key}
            except UploadRejected as e:
                self.store.delete(row.object_key)
                values = {"status": "REJECTED", "reject_reason": str(e)}
            conn.execute(update(t.uploads).where(t.uploads.c.upload_id == upload_id).values(**values))
            append_audit(conn, actor.tenant_id, actor.user_id, "upload.scanned", upload_id,
                         {"status": values["status"]}, now)
            row = conn.execute(select(t.uploads).where(t.uploads.c.upload_id == upload_id)).one()
        return self._view(row)

    def upload_direct(self, actor: Actor, filename: str, content_type: str, data: bytes) -> dict:
        """Server-side path for the web form: same quarantine and scan steps, one request."""
        if len(data) > self.max_bytes:
            raise PayloadTooLarge(f"Files can be up to {self.max_bytes // 1_000_000} MB.", "file")
        created = self.create(actor, filename, content_type, max(1, len(data)))
        exp = int(created["upload_url"].split("exp=")[1].split("&")[0])
        sig = created["upload_url"].split("sig=")[1]
        self.put_blob(created["upload_id"], exp, sig, data)
        return self.complete(actor, created["upload_id"])

    @staticmethod
    def _view(row) -> dict:
        return {"upload_id": row.upload_id, "filename": row.filename, "status": row.status, "size": row.size,
                "sha256": row.sha256, "reject_reason": row.reject_reason}

    def clean_ids(self, actor: Actor, ids: list[str]) -> list[str]:
        if not ids:
            return []
        with self.engine.connect() as conn:
            rows = conn.execute(select(t.uploads.c.upload_id).where(
                t.uploads.c.upload_id.in_(ids), t.uploads.c.tenant_id == actor.tenant_id,
                t.uploads.c.status == "CLEAN")).scalars().all()
        return list(rows)
