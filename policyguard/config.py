"""PolicyGuard settings. Values come from the environment (and an optional git-ignored .env.local)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    """Read KEY=VALUE lines into os.environ without overriding existing values. Values are never printed."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def _decimal(name: str) -> Decimal | None:
    raw = os.environ.get(name, "").strip()
    return Decimal(raw) if raw else None


@dataclass
class PGSettings:
    database_url: str = "postgresql+psycopg://policyguard@127.0.0.1:55432/policyguard"
    redis_url: str | None = "redis://127.0.0.1:56379/0"
    storage_dir: Path = BASE_DIR / ".local" / "objects"
    # Inference. Paid inference stays off unless a model, a key and a budget are all set.
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    nebius_model_id: str | None = None
    nebius_api_key: str | None = field(default=None, repr=False)
    nebius_timeout_s: float = 30.0
    budget_usd: Decimal | None = None
    max_paid_calls: int = 0
    price_in_per_mtok: Decimal = Decimal("0.06")    # Nebius list price for the configured model, USD per 1M tokens
    price_out_per_mtok: Decimal = Decimal("0.24")
    max_output_tokens: int = 1200
    # Worker
    lease_seconds: int = 30
    max_attempts: int = 3
    job_deadline_seconds: int = 1800
    # Uploads
    upload_signing_key: bytes = field(default=b"", repr=False)
    max_upload_bytes: int = 1_500_000   # stays under the app's 2 MB request limit
    upload_ttl_seconds: int = 600
    # Auth for /v1 (JWT). The dev JWKS lives in .local/ and is never committed.
    jwt_issuer: str = "https://idp.policyguard.localhost"
    jwt_audience: str = "policyguard-api"
    jwks_path: Path = BASE_DIR / ".local" / "dev_jwks.json"
    rate_per_minute: int = 60
    rate_burst: int = 20

    @property
    def paid_inference_enabled(self) -> bool:
        return bool(self.nebius_model_id and self.nebius_api_key and self.budget_usd and self.budget_usd > 0
                     and self.max_paid_calls > 0)

    @classmethod
    def from_env(cls) -> PGSettings:
        load_env_file(BASE_DIR / ".env.local")
        s = cls()
        s.database_url = os.environ.get("PG_DATABASE_URL", s.database_url)
        s.redis_url = os.environ.get("PG_REDIS_URL", s.redis_url) or None
        if os.environ.get("PG_STORAGE_DIR"):
            s.storage_dir = Path(os.environ["PG_STORAGE_DIR"])
        s.nebius_base_url = os.environ.get("NEBIUS_BASE_URL", s.nebius_base_url)
        s.nebius_model_id = os.environ.get("NEBIUS_MODEL_ID") or None
        s.nebius_api_key = os.environ.get("NEBIUS_API_KEY") or None
        s.budget_usd = _decimal("PG_INFERENCE_BUDGET_USD")
        s.max_paid_calls = int(os.environ.get("PG_MAX_PAID_CALLS", "0") or 0)
        if os.environ.get("PG_PRICE_IN_PER_MTOK"):
            s.price_in_per_mtok = Decimal(os.environ["PG_PRICE_IN_PER_MTOK"])
        if os.environ.get("PG_PRICE_OUT_PER_MTOK"):
            s.price_out_per_mtok = Decimal(os.environ["PG_PRICE_OUT_PER_MTOK"])
        key = os.environ.get("PG_UPLOAD_SIGNING_KEY", "")
        s.upload_signing_key = key.encode() if key else os.urandom(32)
        return s
