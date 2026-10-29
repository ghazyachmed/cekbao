"""Fixtures for PolicyGuard integration tests against the local PostgreSQL test database."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from policyguard.config import BASE_DIR, PGSettings

PG_TEST_URL = os.environ.get("PG_TEST_DATABASE_URL",
                             "postgresql+psycopg://policyguard@127.0.0.1:55432/policyguard_test")


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


@pytest.fixture(scope="session")
def pg_engine():
    engine = create_engine(PG_TEST_URL, pool_size=10, max_overflow=10)
    try:
        engine.connect().close()
    except OperationalError:
        pytest.skip("PostgreSQL test database not reachable: run scripts/policyguard_local.sh start")
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.attributes["url"] = PG_TEST_URL
    command.upgrade(cfg, "head")
    return engine


@pytest.fixture
def db(pg_engine):
    with pg_engine.begin() as conn:
        names = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                                  "AND tablename <> 'alembic_version'")).scalars().all()
        conn.execute(text("TRUNCATE " + ", ".join(names) + " RESTART IDENTITY CASCADE"))
    return pg_engine


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def pg_settings() -> PGSettings:
    s = PGSettings(database_url=PG_TEST_URL, redis_url=None, upload_signing_key=b"test-signing-key-0123456789")
    s.lease_seconds = 30
    s.max_attempts = 3
    return s
