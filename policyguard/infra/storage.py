"""Private object storage with quarantine, plus HMAC-signed, short-lived upload URLs.

``LocalObjectStore`` writes under .local/objects (git-ignored, never served statically).
``S3ObjectStore`` is the cloud adapter (tested against the moto emulator; no real bucket is used).
"""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def move(self, src: str, dst: str) -> None: ...


class LocalObjectStore:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("object key escapes the store")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def move(self, src: str, dst: str) -> None:
        d = self._path(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        self._path(src).replace(d)


class S3ObjectStore:
    def __init__(self, client, bucket: str):
        self.client, self.bucket = client, bucket

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def move(self, src: str, dst: str) -> None:
        self.client.copy_object(Bucket=self.bucket, Key=dst, CopySource={"Bucket": self.bucket, "Key": src},
                                ServerSideEncryption="AES256")
        self.delete(src)


def sign(secret: bytes, upload_id: str, expires: int) -> str:
    return hmac.new(secret, f"{upload_id}:{expires}".encode(), hashlib.sha256).hexdigest()


def verify(secret: bytes, upload_id: str, expires: int, signature: str, now: int) -> bool:
    return expires > now and hmac.compare_digest(sign(secret, upload_id, expires), signature)
