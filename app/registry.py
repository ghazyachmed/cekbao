"""Read-only trusted-channel registry.

The registry file is reviewed by a human before deployment. The application
loads it once, records its SHA-256 digest and exposes read-only copies. No API
endpoint and no model output can write to it.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApprovedChannel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel_id: str
    method: str
    description: str
    beneficiary_name: str | None = None
    beneficiary_account: str | None = None
    virtual_account_prefix: str | None = None
    virtual_account_length: int | None = None
    swift_bic: str | None = None
    bank_name: str | None = None
    bank_country: str | None = None
    payment_host: str | None = None

    def account_matches(self, account: str | None) -> bool:
        if not account:
            return False
        acct = re.sub(r"[\s-]", "", account)
        if self.beneficiary_account and acct == self.beneficiary_account:
            return True
        if self.virtual_account_prefix and self.virtual_account_length:
            return acct.startswith(self.virtual_account_prefix) and len(acct) == self.virtual_account_length
        return False


class OfficialContact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    office: str
    email: str
    phone: str | None = None
    contact_page_url: str


class PolicyStatement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement_id: str
    text: str


class RegistrySource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    retrieved: date
    reviewed_by: str
    permitted_channel_note: str


class InstitutionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    institution_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    synthetic: bool
    country: str
    official_domains: list[str]
    official_contact: OfficialContact
    approved_channels: list[ApprovedChannel]
    policy_statements: list[PolicyStatement] = Field(default_factory=list)
    source: RegistrySource

    @model_validator(mode="after")
    def _real_entries_need_provenance(self) -> "InstitutionEntry":
        if not self.synthetic:
            if not self.source.url.startswith("https://") or "example" in self.source.url:
                raise ValueError(f"{self.institution_id}: real entries need a reviewed https source URL")
            if not self.source.reviewed_by.strip():
                raise ValueError(f"{self.institution_id}: real entries need a named reviewer")
        return self

    def statement(self, statement_id: str) -> PolicyStatement | None:
        return next((s for s in self.policy_statements if s.statement_id == statement_id), None)


class RegistryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: str
    notice: str
    institutions: list[InstitutionEntry]


def _norm(name: str) -> str:
    name = re.sub(r"\(synthetic\)", "", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip().casefold()


class Registry:
    def __init__(self, path: Path):
        raw = path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        parsed = RegistryFile.model_validate(json.loads(raw))
        self.version = parsed.registry_version
        self.notice = parsed.notice
        self._entries = {e.institution_id: e for e in parsed.institutions}
        self._names: dict[str, str] = {}
        for e in parsed.institutions:
            for n in [e.display_name, *e.aliases]:
                self._names[_norm(n)] = e.institution_id

    def get(self, institution_id: str | None) -> InstitutionEntry | None:
        if not institution_id:
            return None
        e = self._entries.get(institution_id)
        return e.model_copy(deep=True) if e else None

    def resolve(self, name: str | None) -> InstitutionEntry | None:
        """Exact match on normalized name or alias. No fuzzy matching."""
        if not name:
            return None
        iid = self._names.get(_norm(name))
        return self.get(iid)

    def find_in_text(self, text: str) -> InstitutionEntry | None:
        low = text.casefold()
        for norm_name, iid in sorted(self._names.items(), key=lambda kv: -len(kv[0])):
            if norm_name and norm_name in low:
                return self.get(iid)
        return None

    def public_list(self) -> list[dict]:
        return [
            {
                "institution_id": e.institution_id,
                "display_name": e.display_name,
                "synthetic": e.synthetic,
                "country": e.country,
                "official_domains": list(e.official_domains),
                "source_url": e.source.url,
                "retrieved": e.source.retrieved.isoformat(),
            }
            for e in self._entries.values()
        ]
