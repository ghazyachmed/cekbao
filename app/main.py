"""FastAPI application: routes, session handling and security headers."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Iterator

import httpx
from fastapi import Body, Depends, FastAPI, File, Form, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

from . import audit, auth
from .config import Settings
from .db import connect, init_db
from .export import build_bundle, bundle_json_bytes, render_html
from .llm import LLMExtractor
from .registry import Registry
from .settlement import BankFeedTool, LedgerTool
from .workflow import (CreateCase, PlanDecisionRequest, ProposePlanRequest, QuotesRequest, Services, WorkflowError,
                       add_upload, analyze_case, approve_plan, case_view, create_case, deny_plan, list_cases,
                       office_escalations, propose_plan, submit_quotes)

APP_DIR = Path(__file__).parent
API_CSP = "default-src 'none'; frame-ancestors 'none'"
PAGE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
EVIDENCE_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'"


def load_samples(fixtures_dir: Path) -> dict:
    """Synthetic sample inputs with message files inlined."""
    data = json.loads((fixtures_dir / "samples.json").read_text())
    for item in data["tuition_requests"]:
        item["message"] = (fixtures_dir / item.pop("message_file")).read_text()
    for item in data["payment_evidence"]:
        item["offer_message"] = (fixtures_dir / item.pop("offer_message_file")).read_text()
    for item in data.get("evaluation_only", []):
        item["message"] = (fixtures_dir / item.pop("message_file")).read_text()
    return data


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(pattern=r"^[a-z0-9_]{3,40}$")
    access_code: str = Field(min_length=4, max_length=100)


def create_app(settings: Settings | None = None, llm_transport: httpx.BaseTransport | None = None,
               policyguard=None) -> FastAPI:
    """``policyguard``: a PolicyGuard Runtime, or None to read PG_ENABLED from the environment."""
    settings = settings or Settings.from_env()
    init_db(settings.db_path)
    registry = Registry(settings.registry_path)
    ledger = LedgerTool(settings.fixtures_dir / "ledgers" / "ucn_institution_ledger.json")
    bank = BankFeedTool(settings.fixtures_dir / "ledgers" / "sandbox_bank_feed.json")
    llm = None
    if settings.llm_configured:
        llm = LLMExtractor(settings.llm_base_url, settings.llm_model, settings.llm_api_key, registry,
                           transport=llm_transport, timeout_s=settings.llm_timeout_s)
    svc = Services(settings=settings, registry=registry, ledger=ledger, bank=bank, llm=llm)
    if settings.demo_users:
        conn = connect(settings.db_path)
        try:
            auth.seed_demo_users(conn, settings.fixtures_dir / "demo_users.json", settings.pbkdf2_iterations)
        finally:
            conn.close()

    app = FastAPI(title="CEKBAO", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.svc = svc
    pages = Environment(loader=FileSystemLoader(APP_DIR / "templates"), autoescape=select_autoescape(["html"]))
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

    @app.middleware("http")
    async def guard(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_request_bytes:
            return JSONResponse({"detail": "request body too large"}, status_code=413)
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy",
                                    API_CSP if request.url.path.startswith("/api/") else PAGE_CSP)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(auth.AuthError)
    async def _auth_err(_: Request, exc: auth.AuthError):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    @app.exception_handler(WorkflowError)
    async def _wf_err(_: Request, exc: WorkflowError):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _val_err(_: Request, exc: RequestValidationError):
        # Do not echo submitted values back. Return location and message only.
        errors = [{"loc": [str(p) for p in e.get("loc", [])], "msg": str(e.get("msg", ""))[:200]}
                  for e in exc.errors()]
        return JSONResponse({"detail": "validation failed", "errors": errors[:20]}, status_code=422)

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = connect(settings.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def get_session(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> auth.Session:
        return auth.resolve_session(conn, request.cookies.get(auth.SESSION_COOKIE), svc.now())

    def get_session_csrf(session: auth.Session = Depends(get_session),
                         x_csrf_token: str | None = Header(default=None)) -> auth.Session:
        auth.check_csrf(session, x_csrf_token)
        return session

    # ------------------------------------------------------------ pages

    @app.get("/", response_class=HTMLResponse)
    def index():
        return pages.get_template("index.html").render(llm_configured=settings.llm_configured)

    # ------------------------------------------------------------ public

    @app.get("/api/health")
    def health():
        return {"status": "ok", "sandbox": True,
                "extraction_mode": "LLM_TOOL_CALLING" if settings.llm_configured else "DETERMINISTIC_DEMO",
                "llm_configured": settings.llm_configured, "registry_version": registry.version,
                "registry_sha256": registry.sha256}

    @app.get("/api/registry")
    def registry_list():
        return {"notice": registry.notice, "version": registry.version, "sha256": registry.sha256,
                "institutions": registry.public_list()}

    @app.get("/api/samples")
    def samples():
        return load_samples(settings.fixtures_dir)

    # ------------------------------------------------------------ session

    @app.post("/api/session/login")
    def login(body: LoginRequest, conn: sqlite3.Connection = Depends(get_conn)):
        now = svc.now()
        try:
            token, session = auth.login(conn, body.user_id, body.access_code, now, settings.session_ttl_minutes,
                                        settings.pbkdf2_iterations)
        except auth.AuthError as exc:
            audit.log_access(conn, now, body.user_id, "login", None, f"refused {exc.status}")
            raise
        audit.log_access(conn, now, session.user.user_id, "login", None, "ok")
        resp = JSONResponse({"user": {"user_id": session.user.user_id, "display_name": session.user.display_name,
                                      "role": session.user.role, "institution_id": session.user.institution_id,
                                      "payer_reference": session.user.payer_reference},
                             "csrf_token": session.csrf_token, "expires_at": session.expires_at})
        resp.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="strict", secure=settings.cookie_secure,
                        max_age=settings.session_ttl_minutes * 60, path="/")
        return resp

    @app.post("/api/session/logout")
    def logout(request: Request, session: auth.Session = Depends(get_session_csrf),
               conn: sqlite3.Connection = Depends(get_conn)):
        auth.logout(conn, request.cookies.get(auth.SESSION_COOKIE))
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(auth.SESSION_COOKIE, path="/")
        return resp

    @app.get("/api/session/me")
    def me(session: auth.Session = Depends(get_session)):
        u = session.user
        return {"user": {"user_id": u.user_id, "display_name": u.display_name, "role": u.role,
                         "institution_id": u.institution_id, "payer_reference": u.payer_reference},
                "csrf_token": session.csrf_token, "expires_at": session.expires_at}

    # ------------------------------------------------------------ cases

    @app.get("/api/cases")
    def cases(session: auth.Session = Depends(get_session), conn: sqlite3.Connection = Depends(get_conn)):
        return {"cases": list_cases(conn, session)}

    @app.post("/api/cases", status_code=201)
    def new_case(payload: CreateCase = Body(...), session: auth.Session = Depends(get_session_csrf),
                 conn: sqlite3.Connection = Depends(get_conn)):
        return create_case(conn, svc, session, payload)

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, session: auth.Session = Depends(get_session),
                 conn: sqlite3.Connection = Depends(get_conn)):
        return case_view(conn, svc, session, case_id)

    @app.post("/api/cases/{case_id}/analyze")
    def analyze(case_id: str, session: auth.Session = Depends(get_session_csrf),
                conn: sqlite3.Connection = Depends(get_conn)):
        return analyze_case(conn, svc, session, case_id)

    @app.post("/api/cases/{case_id}/quotes")
    def quotes(case_id: str, body: QuotesRequest, session: auth.Session = Depends(get_session_csrf),
               conn: sqlite3.Connection = Depends(get_conn)):
        return submit_quotes(conn, svc, session, case_id, body)

    @app.post("/api/cases/{case_id}/plan/propose")
    def plan_propose(case_id: str, body: ProposePlanRequest, session: auth.Session = Depends(get_session_csrf),
                     conn: sqlite3.Connection = Depends(get_conn)):
        return propose_plan(conn, svc, session, case_id, body)

    @app.post("/api/cases/{case_id}/plan/approve")
    def plan_approve(case_id: str, body: PlanDecisionRequest, session: auth.Session = Depends(get_session_csrf),
                     idempotency_key: str | None = Header(default=None),
                     conn: sqlite3.Connection = Depends(get_conn)):
        response, replayed = approve_plan(conn, svc, session, case_id, body, idempotency_key)
        return JSONResponse({**response, "idempotent_replay": replayed})

    @app.post("/api/cases/{case_id}/plan/deny")
    def plan_deny(case_id: str, body: PlanDecisionRequest, session: auth.Session = Depends(get_session_csrf),
                  conn: sqlite3.Connection = Depends(get_conn)):
        return deny_plan(conn, svc, session, case_id, body)

    @app.post("/api/cases/{case_id}/uploads", status_code=201)
    async def upload(case_id: str, file: UploadFile = File(...), slip_id: str | None = Form(default=None),
                     session: auth.Session = Depends(get_session_csrf), conn: sqlite3.Connection = Depends(get_conn)):
        data = await file.read(settings.max_upload_bytes + 1)
        return add_upload(conn, svc, session, case_id, slip_id, file.filename, data)

    @app.get("/api/cases/{case_id}/evidence.json")
    def evidence_json(case_id: str, session: auth.Session = Depends(get_session),
                      conn: sqlite3.Connection = Depends(get_conn)):
        bundle = build_bundle(conn, svc, session, case_id)
        audit.log_access(conn, svc.now(), session.user.user_id, "export_json", case_id, "ok")
        return Response(bundle_json_bytes(bundle), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="cekbao-{case_id}.json"'})

    @app.get("/api/cases/{case_id}/evidence.html")
    def evidence_html(case_id: str, session: auth.Session = Depends(get_session),
                      conn: sqlite3.Connection = Depends(get_conn)):
        bundle = build_bundle(conn, svc, session, case_id)
        audit.log_access(conn, svc.now(), session.user.user_id, "export_html", case_id, "ok")
        return HTMLResponse(render_html(bundle), headers={
            "Content-Disposition": f'attachment; filename="cekbao-{case_id}.html"',
            "Content-Security-Policy": EVIDENCE_CSP})

    if policyguard is None and os.environ.get("PG_ENABLED") == "1":
        from policyguard.runtime import build_runtime
        policyguard = build_runtime()
    if policyguard is not None:
        from policyguard.web.routes import install as install_policyguard
        install_policyguard(app, policyguard, settings)

    @app.get("/api/office/escalations")
    def escalations(session: auth.Session = Depends(get_session), conn: sqlite3.Connection = Depends(get_conn)):
        return office_escalations(conn, session)

    return app


app = None


def get_app() -> FastAPI:
    """Uvicorn factory entry point: `uvicorn app.main:get_app --factory`."""
    return create_app()
