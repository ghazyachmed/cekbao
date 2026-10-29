"""Token-bucket rate limiting per tenant (fairness: one tenant cannot drain another tenant's bucket).

``RedisTokenBucket`` is atomic across API instances (one Lua script per request).
``InMemoryTokenBucket`` serves tests and the conservative fallback when Redis is unreachable:
the fallback divides the burst by ``fallback_divisor`` because each instance counts on its own.
"""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from typing import Protocol

_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local burst = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local state = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(state[1]) or burst
local ts = tonumber(state[2]) or now
tokens = math.min(burst, tokens + (now - ts) * rate)
local allowed = 0
local wait = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  wait = (cost - tokens) / rate
end
redis.call('HSET', key, 'tokens', tokens, 'ts', now)
redis.call('PEXPIRE', key, math.ceil(burst / rate * 1000) + 1000)
return {allowed, tostring(wait)}
"""


class RateLimiter(Protocol):
    def check(self, key: str, cost: float = 1.0) -> tuple[bool, int]: ...


class InMemoryTokenBucket:
    def __init__(self, rate_per_s: float, burst: float, clock: Callable[[], float] = time.monotonic):
        self.rate, self.burst, self.clock = rate_per_s, burst, clock
        self.state: dict[str, tuple[float, float]] = {}
        self.lock = threading.Lock()

    def check(self, key: str, cost: float = 1.0) -> tuple[bool, int]:
        with self.lock:
            now = self.clock()
            tokens, ts = self.state.get(key, (self.burst, now))
            tokens = min(self.burst, tokens + (now - ts) * self.rate)
            if tokens >= cost:
                self.state[key] = (tokens - cost, now)
                return True, 0
            self.state[key] = (tokens, now)
            return False, max(1, math.ceil((cost - tokens) / self.rate))


class RedisTokenBucket:
    def __init__(self, client, rate_per_s: float, burst: float, fallback_divisor: int = 4,
                 clock: Callable[[], float] = time.time):
        self.client, self.rate, self.burst, self.clock = client, rate_per_s, burst, clock
        self.script = client.register_script(_LUA)
        self.fallback = InMemoryTokenBucket(rate_per_s / fallback_divisor, max(1.0, burst / fallback_divisor))
        self.degraded = False

    def check(self, key: str, cost: float = 1.0) -> tuple[bool, int]:
        try:
            allowed, wait = self.script(keys=[f"pg:rl:{key}"], args=[self.rate, self.burst, self.clock(), cost])
            self.degraded = False
            return bool(int(allowed)), 0 if int(allowed) else max(1, math.ceil(float(wait)))
        except Exception:   # Redis down: keep serving with a stricter local limit instead of failing open
            self.degraded = True
            return self.fallback.check(key, cost)
