"""Server-rendered PolicyGuard pages, mounted into the existing CEKBAO FastAPI app.

Identity comes from the existing CEKBAO session (SQLite sessions, HttpOnly SameSite=Strict cookie, CSRF token).
Pages work without JavaScript; ``app.js`` adds filtering, upload progress and status polling.
"""
from __future__ import annotations

import hashlib
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.datastructures import UploadFile

from app import auth
from app.config import Settings
from app.db import connect
from policyguard.api.v1 import create_router, install_handlers, openapi_route
from policyguard.application.errors import (
    DurableWriteUnavailable,
    IdempotencyConflict,
    NotFound,
    PolicyGuardError,
    ValidationFailed,
)
from policyguard.application.service import Actor, CaseInput
from policyguard.runtime import Runtime
from policyguard.seed import SAMPLES, TENANT

from . import display
from .i18n import t
from .present import present_case

WEB_DIR = Path(__file__).parent
NOT_LISTED = "__not_listed__"
ROLE_MAP = {"student": frozenset({"payer"}), "office_reviewer": frozenset({"reviewer"})}
PRIVATE_PREFIXES = ("/check", "/review", "/v1")
CORRECTABLE = ("payee_name", "account_number", "currency", "swift_bic", "amount")
TIMEZONES = ["UTC", "Europe/London", "Europe/Berlin", "America/New_York", "America/Toronto", "Asia/Singapore",
             "Asia/Jakarta", "Asia/Shanghai", "Australia/Sydney"]


def install(app: FastAPI, rt: Runtime, settings: Settings) -> None:
    env = Environment(loader=FileSystemLoader(WEB_DIR / "templates"), autoescape=select_autoescape(["html"]))
    asset_v = hashlib.sha256(b"".join(f.read_bytes() for f in sorted((WEB_DIR / "static").glob("*.*")))).hexdigest()[:10]
    env.globals.update(asset_v=asset_v, t=t, display=display, samples=SAMPLES, not_listed=NOT_LISTED, timezones=TIMEZONES,
                       max_upload_mb=f"{rt.settings.max_upload_bytes / 1_000_000:.1f} MB")
    app.mount("/pg-static", StaticFiles(directory=WEB_DIR / "static"), name="pg-static")

    if settings.demo_users:
        conn = connect(settings.db_path)
        try:
            auth.seed_demo_users(conn, Path(__file__).parent.parent / "fixtures" / "demo_users.json",
                                 settings.pbkdf2_iterations)
        finally:
            conn.close()

    router = create_router(rt.container, rt.verifier, rt.limiter, rt.store, rt.redis)
    app.include_router(router)
    app.add_api_route("/v1/openapi.json", openapi_route(router), include_in_schema=False)
    install_handlers(app)

    @app.middleware("http")
    async def private_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(PRIVATE_PREFIXES):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    # ------------------------------------------------------------ helpers

    def session_of(request: Request) -> tuple[auth.Session | None, str | None]:
        conn = connect(settings.db_path)
        try:
            return auth.resolve_session(conn, request.cookies.get(auth.SESSION_COOKIE), settings.clock()), None
        except auth.AuthError as e:
            return None, "expired" if "expired" in e.detail else "missing"
        finally:
            conn.close()

    def actor_of(session: auth.Session) -> Actor:
        return Actor(session.user.user_id, TENANT, ROLE_MAP.get(session.user.role, frozenset()))

    def page(name: str, request: Request, session: auth.Session | None, status: int = 200, **ctx) -> HTMLResponse:
        roles = actor_of(session).roles if session else frozenset()
        html = env.get_template(name).render(request_path=request.url.path, session=session, roles=roles,
                                             csrf=session.csrf_token if session else "", **ctx)
        return HTMLResponse(html, status_code=status)

    def to_sign_in(request: Request, reason: str | None) -> RedirectResponse:
        query = f"?next={quote(request.url.path)}" + ("&expired=1" if reason == "expired" else "")
        return RedirectResponse("/check/sign-in" + query, status_code=303)

    def safe_next(value: str | None) -> str:
        return value if value and value.startswith(("/check", "/review")) and "//" not in value else "/check"

    def form_context(actor: Actor, values: dict, errors: list[dict] | None = None, **extra) -> dict:
        institutions = rt.container.intake.institutions(actor)
        return {"institutions": institutions, "values": values, "errors": errors or [],
                "error_fields": {e["field"] for e in errors or []},
                "idempotency_token": values.get("idempotency_token") or secrets.token_urlsafe(16), **extra}

    # ------------------------------------------------------------ sign-in

    @app.get("/check/sign-in", response_class=HTMLResponse)
    def sign_in_page(request: Request, next: str | None = None, expired: str | None = None):
        return page("sign_in.html", request, None, next_url=safe_next(next),
                    message=t("signin.expired") if expired else None, carry={})

    @app.post("/check/sign-in")
    async def sign_in(request: Request):
        form = await request.form()
        user_id, code = str(form.get("user_id", ""))[:40], str(form.get("access_code", ""))[:100]
        carry = {k[6:]: str(v) for k, v in form.items() if k.startswith("carry_")}
        conn = connect(settings.db_path)
        try:
            token, session = auth.login(conn, user_id, code, settings.clock(), settings.session_ttl_minutes,
                                        settings.pbkdf2_iterations)
        except auth.AuthError as e:
            msg = t("signin.failed") if e.status == 401 else e.detail
            return page("sign_in.html", request, None, status=e.status, next_url=safe_next(str(form.get("next") or "")),
                        errors=[{"field": "user_id", "message": msg}], carry=carry, user_id=user_id)
        finally:
            conn.close()
        if carry:   # restore the instruction the user was submitting when the session ended (not submitted yet)
            values = {**carry, "idempotency_token": secrets.token_urlsafe(16)}
            resp: Response = page("check_form.html", request, session, **form_context(actor_of(session), values))
        else:
            resp = RedirectResponse(safe_next(str(form.get("next") or "")), status_code=303)
        resp.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="strict", secure=settings.cookie_secure,
                        max_age=settings.session_ttl_minutes * 60, path="/")
        return resp

    @app.post("/check/sign-out")
    async def sign_out(request: Request):
        form = await request.form()
        session, _ = session_of(request)
        if session is not None:
            auth.check_csrf(session, str(form.get("csrf_token", "")))
            conn = connect(settings.db_path)
            try:
                auth.logout(conn, request.cookies.get(auth.SESSION_COOKIE))
            finally:
                conn.close()
        resp = RedirectResponse("/check/sign-in", status_code=303)
        resp.delete_cookie(auth.SESSION_COOKIE, path="/")
        return resp

    # ------------------------------------------------------------ check form

    @app.get("/check", response_class=HTMLResponse)
    def check_page(request: Request, example: str | None = None, correct: str | None = None):
        session, problem = session_of(request)
        if session is None:
            return to_sign_in(request, problem)
        actor = actor_of(session)
        values: dict[str, Any] = {}
        if example in SAMPLES:
            sample = SAMPLES[example]["input"]
            values = {**{k: v for k, v in sample.items() if v is not None}, "example": example,
                      "institution_choice": sample["institution_id"]}
        elif correct:
            try:
                view = rt.container.intake.get_case(actor, correct)
            except NotFound:
                return page("not_found.html", request, session, status=404)
            claim = view.get("claim") or {}
            values = {"instruction_text": view["instruction_text"], "institution_choice": view["institution_id"] or NOT_LISTED,
                      "institution_query": view["institution_query"] or "",
                      "due_on": display.date_iso(view["due_at"], view["payment_tz"]),
                      "paid_on": display.date_iso(view["paid_at"], view["payment_tz"]),
                      "payment_tz": view["payment_tz"], "correcting": correct,
                      **{f"corr_{k}": (claim.get(k) or {}).get("value", "") for k in CORRECTABLE}}
        return page("check_form.html", request, session, **form_context(actor, values))

    @app.post("/check")
    async def submit_check(request: Request):
        form = await request.form()
        values: dict[str, Any] = {k: (v if isinstance(v, str) else "") for k, v in form.items() if k != "document"}
        values["upload_ids"] = [str(v) for v in form.getlist("upload_ids") if isinstance(v, str)]
        session, problem = session_of(request)
        if session is None:
            carry = {k: v for k, v in values.items() if isinstance(v, str) and k not in ("csrf_token",)}
            return page("sign_in.html", request, None, status=401, next_url="/check", message=t("signin.expired"),
                        carry=carry)
        try:
            auth.check_csrf(session, values.get("csrf_token"))
        except auth.AuthError:
            return page("check_form.html", request, session, status=403,
                        **form_context(actor_of(session), values, [{"field": "instruction_text",
                                                                    "message": "Your form expired. Reload the page."}]))
        actor = actor_of(session)
        errors = _validate(values)
        doc = form.get("document")
        if isinstance(doc, UploadFile) and doc.filename:
            data = await doc.read()
            try:
                up = rt.uploads.upload_direct(actor, doc.filename, doc.content_type or "", data)
                if up["status"] == "CLEAN":
                    values["upload_ids"].append(up["upload_id"])
                else:
                    errors.append({"field": "document", "message": t("check.upload_rejected", reason=up["reject_reason"])})
            except ValidationFailed as e:
                errors.append({"field": "document", "message": e.detail})
        if errors:
            return page("check_form.html", request, session, status=422, **form_context(actor, values, errors))
        ok, retry = rt.limiter.check(f"{actor.tenant_id}:write")
        if not ok:
            return page("check_form.html", request, session, status=429,
                        **form_context(actor, values, banner=t("errors.rate_limited", seconds=retry)))
        payload = _case_input(values, rt.container.intake.institutions(actor),
                              rt.uploads.clean_ids(actor, values["upload_ids"]))
        try:
            result = rt.container.intake.submit(actor, f"web:{actor.user_id}:{values.get('idempotency_token', '')}",
                                                payload)
        except ValidationFailed as e:
            field = {"Idempotency-Key": "instruction_text"}.get(e.field or "", e.field or "instruction_text")
            return page("check_form.html", request, session, status=422,
                        **form_context(actor, values, [{"field": field, "message": e.detail}]))
        except IdempotencyConflict:
            values["idempotency_token"] = secrets.token_urlsafe(16)
            return page("check_form.html", request, session, status=409,
                        **form_context(actor, values, banner=t("errors.form_reused")))
        except DurableWriteUnavailable:
            return page("check_form.html", request, session, status=503,
                        **form_context(actor, values, banner=t("errors.save_failed")))
        return RedirectResponse(f"/check/cases/{result.case_id}", status_code=303)

    @app.post("/check/uploads")
    async def upload(request: Request):
        session, _ = session_of(request)
        if session is None:
            return JSONResponse({"error": "unauthorized", "detail": t("signin.expired")}, status_code=401)
        form = await request.form()
        try:
            auth.check_csrf(session, request.headers.get("X-CSRF-Token") or str(form.get("csrf_token", "")))
        except auth.AuthError as e:
            return JSONResponse({"error": "forbidden", "detail": e.detail}, status_code=403)
        file = form.get("file")
        if not isinstance(file, UploadFile) or not file.filename:
            return JSONResponse({"error": "validation_failed", "detail": "Choose a file."}, status_code=422)
        try:
            return rt.uploads.upload_direct(actor_of(session), file.filename, file.content_type or "", await file.read())
        except PolicyGuardError as e:
            return JSONResponse({"error": e.code, "detail": e.detail}, status_code=e.status)

    # ------------------------------------------------------------ case pages

    @app.get("/check/cases/{case_id}", response_class=HTMLResponse)
    def case_page(request: Request, case_id: str):
        session, problem = session_of(request)
        if session is None:
            return to_sign_in(request, problem)
        try:
            view = rt.container.intake.get_case(actor_of(session), case_id)
        except NotFound:
            return page("not_found.html", request, session, status=404)
        return page("case.html", request, session, case=present_case(view))

    @app.get("/check/cases/{case_id}/status.json")
    def case_status(request: Request, case_id: str):
        session, _ = session_of(request)
        if session is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            view = rt.container.intake.get_case(actor_of(session), case_id)
        except NotFound:
            return JSONResponse({"error": "not_found"}, status_code=404)
        job = view["job"] or {}
        state = display.job_state(view["state"], job.get("run_after") if view["state"] == "RETRY_WAIT" else None)
        return {**state, "attempts": job.get("attempts", 0), "max_attempts": job.get("max_attempts")}

    @app.get("/check/history", response_class=HTMLResponse)
    def history(request: Request):
        session, problem = session_of(request)
        if session is None:
            return to_sign_in(request, problem)
        own = Actor(session.user.user_id, TENANT, frozenset({"payer"}))   # history lists only your own checks
        rows = rt.container.intake.list_cases(own)
        return page("history.html", request, session, rows=rows)

    # ------------------------------------------------------------ reviewer workspace

    def reviewer(request: Request):
        session, problem = session_of(request)
        if session is None:
            return None, to_sign_in(request, problem)
        if "reviewer" not in actor_of(session).roles:
            return None, page("forbidden.html", request, session, status=403)
        return session, None

    @app.get("/review", response_class=HTMLResponse)
    def review_queue(request: Request, filter: str = "needs"):
        session, denied = reviewer(request)
        if denied:
            return denied
        rows = rt.container.intake.list_cases(actor_of(session), needs_review=filter != "all")
        return page("review_list.html", request, session, rows=rows, filter=filter)

    def review_page(request, session, case_id, status=200, errors=None, values=None, banner=None):
        try:
            view = rt.container.intake.get_case(actor_of(session), case_id)
        except NotFound:
            return page("not_found.html", request, session, status=404)
        return page("review_case.html", request, session, status=status, case=present_case(view),
                    errors=errors or [], error_fields={e["field"] for e in errors or []}, values=values or {},
                    banner=banner, recorded=request.query_params.get("recorded") == "1")

    @app.get("/review/cases/{case_id}", response_class=HTMLResponse)
    def review_case(request: Request, case_id: str):
        session, denied = reviewer(request)
        return denied or review_page(request, session, case_id)

    @app.post("/review/cases/{case_id}")
    async def submit_review(request: Request, case_id: str):
        session, denied = reviewer(request)
        if denied:
            return denied
        form = {k: str(v) for k, v in (await request.form()).items()}
        try:
            auth.check_csrf(session, form.get("csrf_token"))
        except auth.AuthError:
            return review_page(request, session, case_id, 403, banner="Your form expired. Reload the page.")
        errors = []
        if form.get("outcome") not in ("CONFIRMED", "CORRECTED", "NEEDS_MORE_INFORMATION"):
            errors.append({"field": "outcome", "message": "Choose an outcome."})
        if len(form.get("reason", "").strip()) < 10:
            errors.append({"field": "reason", "message": "Give a reason of at least 10 characters."})
        if errors:
            return review_page(request, session, case_id, 422, errors, form)
        try:
            rt.container.reviews.submit(actor_of(session), case_id, form["outcome"], form["reason"],
                                        int(form.get("row_version") or 0))
        except PolicyGuardError as e:
            banner = t("review.stale") if e.status == 409 else e.detail
            return review_page(request, session, case_id, e.status, values=form, banner=banner)
        return RedirectResponse(f"/review/cases/{case_id}?recorded=1", status_code=303)

    # ------------------------------------------------------------ crawlers

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots(request: Request):
        sitemap = str(request.base_url).rstrip("/") + "/sitemap.xml"   # robots.txt requires an absolute URL
        return f"User-agent: *\nDisallow: /check\nDisallow: /review\nDisallow: /v1\nDisallow: /api\nSitemap: {sitemap}\n"

    @app.get("/sitemap.xml")
    def sitemap(request: Request):
        base = str(request.base_url).rstrip("/")
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               f"<url><loc>{base}/</loc></url></urlset>\n")
        return Response(xml, media_type="application/xml")


def _validate(values: dict) -> list[dict]:
    errors = []
    if len(values.get("instruction_text", "").strip()) < 20:
        errors.append({"field": "instruction_text",
                       "message": "Paste the full payment instruction (at least 20 characters)."})
    choice = values.get("institution_choice", "")
    if not choice:
        errors.append({"field": "institution_choice", "message": "Choose an institution, or choose that it is not listed."})
    elif choice == NOT_LISTED and not values.get("institution_query", "").strip():
        errors.append({"field": "institution_query", "message": "Type the institution's name."})
    if not values.get("due_on"):
        errors.append({"field": "due_on", "message": t("errors.due_required")})
    for name in ("due_on", "paid_on", "instruction_received_on"):
        value = values.get(name, "")
        if value and not display.is_iso_date(value):
            errors.append({"field": name, "message": t("errors.date")})
    return errors


def _case_input(values: dict, institutions: list[dict], upload_ids: list[str]) -> CaseInput:
    choice = values.get("institution_choice", "")
    inst = next((i for i in institutions if i["institution_id"] == choice), None)
    tz = values.get("payment_tz") or (inst["timezone"] if inst else "UTC")
    corrections = {k: values[f"corr_{k}"].strip() for k in CORRECTABLE if values.get(f"corr_{k}", "").strip()}
    return CaseInput(instruction_text=values.get("instruction_text", ""),
                     institution_id=inst["institution_id"] if inst else None,
                     institution_query=values.get("institution_query", "").strip() or None if not inst else None,
                     instruction_received_on=values.get("instruction_received_on") or None,
                     paid_on=values.get("paid_on") or None, due_on=values.get("due_on") or None, payment_tz=tz,
                     corrections=corrections, upload_ids=tuple(upload_ids))
