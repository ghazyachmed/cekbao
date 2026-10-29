"""Composition root: builds every adapter from settings. Used by the web app, the API and the worker."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, create_engine

from .application.service import Actor, Container, build_container
from .application.uploads import UploadService
from .config import PGSettings
from .infra.auth import JwtVerifier, Unauthorized
from .infra.ratelimit import InMemoryTokenBucket, RateLimiter, RedisTokenBucket
from .infra.storage import LocalObjectStore, ObjectStore


def utcnow() -> datetime:
    return datetime.now(UTC)


class DisabledVerifier:
    def actor(self, authorization: str | None) -> Actor:
        raise Unauthorized("API authentication is not configured on this server.")


@dataclass
class Runtime:
    settings: PGSettings
    engine: Engine
    clock: Callable[[], datetime]
    container: Container
    store: ObjectStore
    uploads: UploadService
    limiter: RateLimiter
    verifier: Any
    redis: Any | None


def build_runtime(settings: PGSettings | None = None, *, engine: Engine | None = None,
                  clock: Callable[[], datetime] | None = None, **container_kw) -> Runtime:
    settings = settings or PGSettings.from_env()
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
    clock = clock or utcnow
    redis_client, cache = None, None
    if settings.redis_url:
        import redis

        from .infra.cache import RedisCache
        redis_client = redis.Redis.from_url(settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)
        cache = RedisCache(redis_client)
    container = build_container(engine, settings, clock, cache=cache, **container_kw)
    rate = settings.rate_per_minute / 60
    limiter: RateLimiter = (RedisTokenBucket(redis_client, rate, settings.rate_burst) if redis_client
                            else InMemoryTokenBucket(rate, settings.rate_burst))
    verifier = (JwtVerifier.from_jwks_file(settings.jwks_path, settings.jwt_issuer, settings.jwt_audience)
                if settings.jwks_path.is_file() else DisabledVerifier())
    store = LocalObjectStore(settings.storage_dir)
    uploads = UploadService(engine, store, clock, settings.upload_signing_key, settings.max_upload_bytes,
                            settings.upload_ttl_seconds)
    return Runtime(settings, engine, clock, container, store, uploads, limiter, verifier, redis_client)
