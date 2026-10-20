"""Server-side sessions, demo sign-in and role checks.

Sandbox sign-in uses per-persona demo access codes from fixtures. They are
test values for this prototype, not real credentials. The server stores a
PBKDF2 hash. Session tokens are random, stored as SHA-256 hashes, sent in an
HttpOnly SameSite=Strict cookie and expire after a fixed TTL. State-changing
requests also need the per-session CSRF token in the X-CSRF-Token header.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

SESSION_COOKIE = "cekbao_session"
MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=15)


@dataclass(frozen=True)
class User:
    user_id: str
    display_name: str
    role: str
    institution_id: str
    payer_reference: str | None


@dataclass(frozen=True)
class Session:
    user: User
    csrf_token: str
    expires_at: str


class AuthError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _hash_code(code: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", code.encode(), salt, iterations)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def seed_demo_users(conn: sqlite3.Connection, users_file: Path, iterations: int) -> None:
    data = json.loads(users_file.read_text())
    for u in data["users"]:
        if conn.execute("SELECT 1 FROM users WHERE user_id = ?", (u["user_id"],)).fetchone():
            continue
        salt = secrets.token_bytes(16)
        conn.execute(
            "INSERT INTO users (user_id, display_name, role, institution_id, payer_reference, code_salt, code_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (u["user_id"], u["display_name"], u["role"], u["institution_id"], u.get("payer_reference"), salt,
             _hash_code(u["demo_access_code"], salt, iterations)))


def _row_to_user(row: sqlite3.Row) -> User:
    return User(row["user_id"], row["display_name"], row["role"], row["institution_id"], row["payer_reference"])


def login(conn: sqlite3.Connection, user_id: str, code: str, now: datetime, ttl_minutes: int,
          iterations: int) -> tuple[str, Session]:
    since = (now - FAILURE_WINDOW).isoformat()
    failures = conn.execute("SELECT COUNT(*) FROM login_failures WHERE user_id = ? AND at > ?",
                            (user_id, since)).fetchone()[0]
    if failures >= MAX_FAILURES:
        raise AuthError(429, "too many failed attempts, try again later")
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    salt = row["code_salt"] if row else b"\x00" * 16
    expected = row["code_hash"] if row else b"\x00" * 32
    ok = hmac.compare_digest(_hash_code(code, salt, iterations), expected) and row is not None
    if not ok:
        conn.execute("INSERT INTO login_failures (user_id, at) VALUES (?, ?)", (user_id, now.isoformat()))
        raise AuthError(401, "invalid user or access code")
    conn.execute("DELETE FROM login_failures WHERE user_id = ?", (user_id,))
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    expires = (now + timedelta(minutes=ttl_minutes)).isoformat()
    conn.execute("INSERT INTO sessions (token_hash, user_id, csrf_token, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                 (_token_hash(token), user_id, csrf, now.isoformat(), expires))
    return token, Session(_row_to_user(row), csrf, expires)


def resolve_session(conn: sqlite3.Connection, token: str | None, now: datetime) -> Session:
    if not token:
        raise AuthError(401, "sign-in required")
    row = conn.execute(
        "SELECT s.csrf_token, s.expires_at, u.* FROM sessions s JOIN users u ON u.user_id = s.user_id "
        "WHERE s.token_hash = ?", (_token_hash(token),)).fetchone()
    if row is None:
        raise AuthError(401, "session not found")
    if datetime.fromisoformat(row["expires_at"]) <= now:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        raise AuthError(401, "session expired")
    return Session(_row_to_user(row), row["csrf_token"], row["expires_at"])


def check_csrf(session: Session, header_value: str | None) -> None:
    if not header_value or not hmac.compare_digest(header_value, session.csrf_token):
        raise AuthError(403, "missing or invalid CSRF token")


def logout(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def require_role(session: Session, *roles: str) -> None:
    if session.user.role not in roles:
        raise AuthError(403, "role not permitted for this action")
