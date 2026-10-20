"""Append-only, hash-chained audit log per case."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime

GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _event_hash(prev_hash: str, event: dict) -> str:
    return hashlib.sha256((prev_hash + canonical(event)).encode()).hexdigest()


def append_event(conn: sqlite3.Connection, case_id: str, actor_id: str, event_type: str, payload: dict,
                 now: datetime) -> str:
    row = conn.execute("SELECT seq, hash FROM audit_events WHERE case_id = ? ORDER BY seq DESC LIMIT 1",
                       (case_id,)).fetchone()
    seq = (row["seq"] + 1) if row else 1
    prev_hash = row["hash"] if row else GENESIS
    event_id = "evt_" + secrets.token_hex(10)
    at = now.isoformat(timespec="seconds")
    body = {"event_id": event_id, "case_id": case_id, "seq": seq, "actor_id": actor_id,
            "event_type": event_type, "at": at, "payload": payload}
    digest = _event_hash(prev_hash, body)
    conn.execute(
        "INSERT INTO audit_events (event_id, case_id, seq, actor_id, event_type, at, payload_json, prev_hash, hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, case_id, seq, actor_id, event_type, at, canonical(payload), prev_hash, digest))
    return event_id


def list_events(conn: sqlite3.Connection, case_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM audit_events WHERE case_id = ? ORDER BY seq", (case_id,)).fetchall()
    return [{"event_id": r["event_id"], "case_id": r["case_id"], "seq": r["seq"], "actor_id": r["actor_id"],
             "event_type": r["event_type"], "at": r["at"], "payload": json.loads(r["payload_json"]),
             "prev_hash": r["prev_hash"], "hash": r["hash"]} for r in rows]


def verify_chain(events: list[dict]) -> bool:
    prev = GENESIS
    for e in events:
        body = {k: e[k] for k in ("event_id", "case_id", "seq", "actor_id", "event_type", "at", "payload")}
        if e["prev_hash"] != prev or _event_hash(prev, body) != e["hash"]:
            return False
        prev = e["hash"]
    return True


def log_access(conn: sqlite3.Connection, now: datetime, actor_id: str | None, action: str,
               case_id: str | None, outcome: str) -> None:
    conn.execute("INSERT INTO access_log (at, actor_id, action, case_id, outcome) VALUES (?, ?, ?, ?, ?)",
                 (now.isoformat(timespec="seconds"), actor_id, action, case_id, outcome))
