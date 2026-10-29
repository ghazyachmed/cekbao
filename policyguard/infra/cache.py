"""Redis snapshot cache. Keys embed tenant, institution and policy epoch, so a policy change or revocation
moves readers to a new key immediately; old entries expire by TTL. Cache errors fall back to the database."""
from __future__ import annotations

import json


class RedisCache:
    def __init__(self, client):
        self.client = client

    def get(self, key: str) -> dict | None:
        try:
            raw = self.client.get(key)
        except Exception:
            return None
        return None if raw is None else json.loads(raw)

    def set(self, key: str, value: dict, ttl_s: int) -> None:
        try:
            self.client.set(key, json.dumps(value, default=str), ex=ttl_s)
        except Exception:
            pass
