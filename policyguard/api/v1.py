"""/v1 HTTP API (OpenAPI at /v1/openapi.json). Bearer JWT, tenant-scoped, idempotent case creation."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from policyguard.application.errors import PolicyGuardError, RateLimited
from policyguard.application.service import Actor, CaseInput, Container
from policyguard.application.uploads import UploadService
from policyguard.infra.auth import JwtVerifier
from policyguard.infra.ratelimit import RateLimiter
from policyguard.infra.storage import ObjectStore
from policyguard.infra.telemetry import tracer

API_VERSION = "1.0.0"


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction_text: str = Field(min_length=1, max_length=20_000, description="The payment instruction, as received.")
    institution_id: str | None = Field(default=None, max_length=64)
    institution_query: str | None = Field(default=None, max_length=200,
                                          description="Institution name when it is not in the registry.")
    instruction_received_on: date | None = None
    paid_on: date | None = Field(default=None, description="Date of a payment already made (historical check).")
    due_on: date | None = Field(default=None, description="Intended payment date (next-payment check).")
    payment_tz: str = Field(default="UTC", max_length=64, description="IANA time zone for the dates.")
    corrections: dict[str, str] = Field(default_factory=dict)
    upload_ids: list[str] = Field(default_factory=list, max_length=5)

    def to_input(self) -> CaseInput:
        iso = lambda d: d.isoformat() if d else None  # noqa: E731
        return CaseInput(instruction_text=self.instruction_text, institution_id=self.institution_id,
                         institution_query=self.institution_query,
                         instruction_received_on=iso(self.instruction_received_on), paid_on=iso(self.paid_on),
                         due_on=iso(self.due_on), payment_tz=self.payment_tz, corrections=dict(self.corrections),
                         upload_ids=tuple(self.upload_ids))


class CaseAccepted(BaseModel):
    case_id: str
    state: str
    status_url: str


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["CONFIRMED", "CORRECTED", "NEEDS_MORE_INFORMATION"]
    reason: str = Field(min_length=10, max_length=2000)


class UploadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=1, max_length=100)
    size: int = Field(gt=0)


def error_body(exc: PolicyGuardError) -> dict:
    out = {"error": exc.code, "detail": exc.detail}
    field = getattr(exc, "field", None)
    if field:
        out["field"] = field
    return out


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(PolicyGuardError)
    async def _pg_error(_: Request, exc: PolicyGuardError):
        headers = {"Retry-After": str(exc.retry_after_s)} if isinstance(exc, RateLimited) else None
        return JSONResponse(error_body(exc), status_code=exc.status, headers=headers)


def create_router(container: Container, verifier: JwtVerifier, limiter: RateLimiter, store: ObjectStore,
                  redis_client=None) -> APIRouter:
    s = container.settings
    uploads = UploadService(container.engine, store, container.intake.clock, s.upload_signing_key, s.max_upload_bytes,
                            s.upload_ttl_seconds)
    router = APIRouter()

    def actor(authorization: str | None = Header(default=None)) -> Actor:
        return verifier.actor(authorization)

    def limited(a: Actor = Depends(actor)) -> Actor:
        ok, retry = limiter.check(f"{a.tenant_id}:write")
        if not ok:
            raise RateLimited(retry)
        return a

    def if_match(value: str | None) -> int:
        if value is None or not value.strip('"').isdigit():
            raise PolicyGuardError("If-Match header with the current row_version is required.")
        return int(value.strip('"'))

    @router.post("/v1/cases", status_code=202, response_model=CaseAccepted, tags=["cases"],
                 responses={409: {"description": "Idempotency-Key reused with another payload"},
                            429: {"description": "Rate limited; see Retry-After"},
                            503: {"description": "The case could not be stored durably"}})
    def create_case(payload: CaseCreate, response: Response, a: Actor = Depends(limited),
                    idempotency_key: str = Header(..., alias="Idempotency-Key", max_length=128)):
        with tracer().start_as_current_span("cases.create"):
            r = container.intake.submit(a, idempotency_key, payload.to_input())
        url = f"/v1/cases/{r.case_id}"
        response.headers["Location"] = url
        if r.replayed:
            response.headers["Idempotent-Replayed"] = "true"
        return CaseAccepted(case_id=r.case_id, state=r.state, status_url=url)

    @router.get("/v1/cases/{case_id}", tags=["cases"])
    def get_case(case_id: str, a: Actor = Depends(actor)):
        return container.intake.get_case(a, case_id)

    @router.post("/v1/cases/{case_id}/reviews", status_code=201, tags=["reviews"])
    def review(case_id: str, payload: ReviewCreate, a: Actor = Depends(limited),
               if_match_header: str | None = Header(default=None, alias="If-Match")):
        rid = container.reviews.submit(a, case_id, payload.outcome, payload.reason, if_match(if_match_header))
        return {"review_id": rid}

    @router.post("/v1/policies/{version_id}/approve", tags=["policies"])
    def approve(version_id: str, a: Actor = Depends(limited),
                if_match_header: str | None = Header(default=None, alias="If-Match")):
        container.policies.approve(a, version_id, if_match(if_match_header))
        return {"version_id": version_id, "approval_status": "APPROVED"}

    @router.post("/v1/uploads", status_code=201, tags=["uploads"])
    def create_upload(payload: UploadCreate, a: Actor = Depends(limited)):
        return uploads.create(a, payload.filename, payload.content_type, payload.size)

    @router.put("/v1/uploads/{upload_id}/blob", status_code=204, tags=["uploads"], include_in_schema=False)
    async def put_blob(upload_id: str, exp: int, sig: str, request: Request):
        uploads.put_blob(upload_id, exp, sig, await request.body())
        return Response(status_code=204)

    @router.post("/v1/uploads/{upload_id}/complete", tags=["uploads"])
    def complete_upload(upload_id: str, a: Actor = Depends(actor)):
        return uploads.complete(a, upload_id)

    @router.get("/healthz", tags=["ops"])
    def healthz():
        return {"status": "ok"}

    @router.get("/readyz", tags=["ops"])
    def readyz():
        checks = {}
        try:
            with container.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "unavailable"
        if redis_client is not None:
            try:
                redis_client.ping()
                checks["redis"] = "ok"
            except Exception:
                checks["redis"] = "degraded"   # limiter falls back; not fatal for readiness
        ready = checks["database"] == "ok"
        return JSONResponse({"ready": ready, "checks": checks}, status_code=200 if ready else 503)

    return router


def openapi_route(router: APIRouter):
    schema_cache: dict = {}

    def openapi_json():
        if not schema_cache:
            schema_cache.update(get_openapi(title="CEKBAO PolicyGuard API", version=API_VERSION,
                                            routes=router.routes,
                                            description="Policy-consistency checks for payment instructions. "
                                                        "A result is never a settlement confirmation."))
        return schema_cache
    return openapi_json


def create_api_app(container: Container, verifier: JwtVerifier, limiter: RateLimiter, store: ObjectStore,
                   redis_client=None) -> FastAPI:
    app = FastAPI(title="CEKBAO PolicyGuard API", version=API_VERSION, docs_url=None, redoc_url=None,
                  openapi_url=None)
    router = create_router(container, verifier, limiter, store, redis_client)
    app.include_router(router)
    app.add_api_route("/v1/openapi.json", openapi_route(router), include_in_schema=False)
    install_handlers(app)

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        errors = [{"loc": [str(p) for p in e.get("loc", [])], "msg": str(e.get("msg", ""))[:200]} for e in exc.errors()]
        return JSONResponse({"error": "validation_failed", "errors": errors[:20]}, status_code=422)
    return app
