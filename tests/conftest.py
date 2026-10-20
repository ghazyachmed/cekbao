from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import FIXTURES_DIR, Settings  # noqa: E402
from app.main import create_app, load_samples  # noqa: E402

CODES = {"stu_ayu": "demo-ayu-2026", "stu_budi": "demo-budi-2026", "stu_citra": "demo-citra-2026",
         "officer_nbu": "demo-officer-2026"}


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 20, 4, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def settings(tmp_path, clock) -> Settings:
    return Settings(db_path=tmp_path / "test.sqlite3", clock=clock, pbkdf2_iterations=1000)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def samples() -> dict:
    return load_samples(FIXTURES_DIR)


class Actor:
    """A signed-in test client with its CSRF token."""

    def __init__(self, app, user_id: str):
        self.client = TestClient(app)
        self.user_id = user_id
        r = self.client.post("/api/session/login", json={"user_id": user_id, "access_code": CODES[user_id]})
        assert r.status_code == 200, r.text
        self.csrf = r.json()["csrf_token"]

    def post(self, url, json=None, headers=None, **kw):
        h = {"X-CSRF-Token": self.csrf, **(headers or {})}
        return self.client.post(url, json=json, headers=h, **kw)

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def new_tuition_case(self, sample: dict) -> dict:
        r = self.post("/api/cases", json={"case_type": "tuition_request",
                                          "claimed_institution": sample["claimed_institution"],
                                          "message": sample["message"]})
        assert r.status_code == 201, r.text
        return r.json()

    def analyze(self, case_id: str) -> dict:
        r = self.post(f"/api/cases/{case_id}/analyze")
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
def login(app):
    def _login(user_id: str) -> Actor:
        return Actor(app, user_id)
    return _login


def sample_by_id(samples: dict, sid: str) -> dict:
    for group in ("tuition_requests", "payment_evidence"):
        for s in samples[group]:
            if s["id"] == sid:
                return s
    raise KeyError(sid)
