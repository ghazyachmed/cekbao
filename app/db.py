"""SQLite storage. One connection per request. Parameterized SQL only."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'office_reviewer')),
    institution_id TEXT NOT NULL,
    payer_reference TEXT,
    code_salt BLOB NOT NULL,
    code_hash BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_failures (
    user_id TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(user_id),
    case_type TEXT NOT NULL CHECK (case_type IN ('tuition_request', 'payment_evidence')),
    institution_id TEXT,
    state TEXT NOT NULL CHECK (state IN ('draft', 'needs_review', 'approved', 'blocked')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    input_json TEXT NOT NULL,
    analysis_json TEXT,
    quotes_json TEXT,
    escalated INTEGER NOT NULL DEFAULT 0,
    intermediary_hash TEXT
);
CREATE TABLE IF NOT EXISTS plans (
    plan_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    revision INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'approved', 'denied', 'superseded')),
    plan_json TEXT NOT NULL,
    digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (case_id, revision)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_approved_plan ON plans(case_id) WHERE status = 'approved';
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    UNIQUE (case_id, seq)
);
CREATE TABLE IF NOT EXISTS idempotency (
    user_id TEXT NOT NULL,
    idem_key TEXT NOT NULL,
    case_id TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, idem_key)
);
CREATE TABLE IF NOT EXISTS slip_index (
    slip_hash TEXT NOT NULL,
    case_id TEXT NOT NULL,
    PRIMARY KEY (slip_hash, case_id)
);
CREATE TABLE IF NOT EXISTS uploads (
    upload_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    slip_id TEXT,
    safe_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    actor_id TEXT,
    action TEXT NOT NULL,
    case_id TEXT,
    outcome TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(path: Path) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()
