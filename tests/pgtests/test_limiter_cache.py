"""Redis token bucket and tenant-scoped snapshot cache against the local Redis (cases 6, 11, 16)."""
from __future__ import annotations

import pytest
import redis

from policyguard.application.service import build_container
from policyguard.infra.cache import RedisCache
from policyguard.infra.pg import PolicySnapshots
from policyguard.infra.ratelimit import RedisTokenBucket
from policyguard.seed import TENANT, load_demo

from .test_intake_queue import ADMIN


@pytest.fixture
def r():
    client = redis.Redis(host="127.0.0.1", port=56379, db=15, socket_timeout=1)
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not reachable: run scripts/policyguard_local.sh start")
    client.flushdb()
    return client


def test_token_bucket_limits_per_key(r):
    bucket = RedisTokenBucket(r, rate_per_s=0.5, burst=3)
    results = [bucket.check("tenant-a:write") for _ in range(4)]
    assert [ok for ok, _ in results] == [True, True, True, False] and results[-1][1] >= 1
    assert bucket.check("tenant-b:write")[0] is True


def test_limiter_degrades_to_stricter_local_limit_when_redis_is_down():
    dead = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)
    bucket = RedisTokenBucket(dead, rate_per_s=1, burst=8, fallback_divisor=4)
    oks = [bucket.check("tenant-a:write")[0] for _ in range(3)]
    assert bucket.degraded and oks == [True, True, False]


def test_snapshot_cache_is_tenant_scoped_and_epoch_keyed(r, db, clock, pg_settings):
    load_demo(db, clock())
    snaps = PolicySnapshots(db, RedisCache(r))
    snap = snaps.load(TENANT, "inst-asterbay")
    assert r.exists(PolicySnapshots.key(TENANT, "inst-asterbay", snap.epoch))
    assert snaps.load("tenant-other", "inst-asterbay").institution is None   # no cross-tenant read


def test_06_revocation_moves_readers_off_the_cached_snapshot(r, db, clock, pg_settings):
    load_demo(db, clock())
    cache = RedisCache(r)
    c = build_container(db, pg_settings, clock, cache=cache)
    before = c.snapshots.load(TENANT, "inst-asterbay")
    c.policies.revoke(ADMIN, "pv-abu-2026", "Account closed", c.policies.row_version("pv-abu-2026"))
    after = c.snapshots.load(TENANT, "inst-asterbay")
    assert after.epoch == before.epoch + 1
    revoked = next(v for v in after.versions if v.version_id == "pv-abu-2026")
    assert revoked.revoked_at is not None
