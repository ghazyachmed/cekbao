"""Application errors. The API layer maps them to HTTP status codes."""
from __future__ import annotations


class PolicyGuardError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, detail: str = ""):
        super().__init__(detail or self.code)
        self.detail = detail or self.code


class ValidationFailed(PolicyGuardError):
    status, code = 422, "validation_failed"

    def __init__(self, detail: str, field: str | None = None):
        super().__init__(detail)
        self.field = field


class NotFound(PolicyGuardError):
    status, code = 404, "not_found"


class Forbidden(PolicyGuardError):
    status, code = 403, "forbidden"


class IdempotencyConflict(PolicyGuardError):
    status, code = 409, "idempotency_key_reused"


class ConcurrencyConflict(PolicyGuardError):
    status, code = 409, "stale_row_version"


class DurableWriteUnavailable(PolicyGuardError):
    status, code = 503, "storage_unavailable"


class RateLimited(PolicyGuardError):
    status, code = 429, "rate_limited"

    def __init__(self, retry_after_s: int):
        super().__init__(f"retry after {retry_after_s} s")
        self.retry_after_s = retry_after_s


class TransientModelError(Exception):
    """Provider 429, 5xx, timeout or partial response. The job may retry."""

    def __init__(self, detail: str, retry_after: float | None = None):
        super().__init__(detail)
        self.retry_after = retry_after


class ModelOutputError(Exception):
    """The model answered, but the answer failed schema validation. Retrying the same input will not help."""


class ModelUnavailable(Exception):
    """Configuration or contract error at the provider (401, 403, 404, 400). Retrying will not help."""


class BudgetExhausted(Exception):
    pass


class LeaseLost(Exception):
    pass


class EpochChanged(Exception):
    pass
