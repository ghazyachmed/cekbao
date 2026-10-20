"""Runtime settings. Values come from environment variables only."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

BASE_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = BASE_DIR / "fixtures"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    db_path: Path = BASE_DIR / "data" / "cekbao.sqlite3"
    fixtures_dir: Path = FIXTURES_DIR
    registry_path: Path = FIXTURES_DIR / "registry.json"
    session_ttl_minutes: int = 30
    max_message_chars: int = 20_000
    max_upload_bytes: int = 1_000_000
    max_request_bytes: int = 2_000_000
    demo_users: bool = True
    cookie_secure: bool = False
    llm_base_url: str | None = None
    llm_model: str | None = None
    # repr=False keeps the key out of logs, tracebacks and debug prints.
    llm_api_key: str | None = field(default=None, repr=False)
    llm_timeout_s: float = 20.0
    pbkdf2_iterations: int = 120_000
    clock: Callable[[], datetime] = field(default=utcnow, repr=False)

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model and self.llm_api_key)

    @classmethod
    def from_env(cls) -> "Settings":
        s = cls()
        if os.environ.get("CEKBAO_DB_PATH"):
            s.db_path = Path(os.environ["CEKBAO_DB_PATH"])
        s.session_ttl_minutes = int(os.environ.get("CEKBAO_SESSION_TTL_MINUTES", s.session_ttl_minutes))
        s.demo_users = _flag("CEKBAO_DEMO_USERS", True)
        s.cookie_secure = _flag("CEKBAO_COOKIE_SECURE", False)
        s.llm_base_url = os.environ.get("LLM_BASE_URL") or None
        s.llm_model = os.environ.get("LLM_MODEL") or None
        s.llm_api_key = os.environ.get("LLM_API_KEY") or None
        return s
