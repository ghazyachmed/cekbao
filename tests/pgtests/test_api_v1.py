"""HTTP contract of /v1 (mandatory cases 11, 12, 16, 18) with real PostgreSQL and signed JWTs."""
from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from policyguard.api.v1 import create_api_app
from policyguard.application.service import build_container
from policyguard.infra.auth import JwtVerifier
from policyguard.infra.ratelimit import InMemoryTokenBucket
from policyguard.infra.storage import LocalObjectStore
from policyguard.seed import DISCOVERED_VERSION_ID, SAMPLES, TENANT, load_demo

ISS, AUD = "https://idp.test.localhost", "policyguard-api"
KEY = ec.generate_private_key(ec.SECP256R1())
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def token(sub="pg_payer", roles=("payer",), tenant=TENANT, amr=("pwd",), exp=3600, aud=AUD, key=PEM, alg="ES256"):
    now = int(time.time())
    claims = {"sub": sub, "tid": tenant, "roles": list(roles), "amr": list(amr), "iss": ISS, "aud": aud,
              "iat": now, "exp": now + exp}
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": "test"})


def auth(**kw) -> dict:
    return {"Authorization": f"Bearer {token(**kw)}"}


def body(name="conflict") -> dict:
    return dict(SAMPLES[name]["input"])


@pytest.fixture
def make_client(db, clock, pg_settings, tmp_path):
    def make(engine=None, burst=100):
        load_demo(db, clock())
        container = build_container(engine or db, pg_settings, clock)
        verifier = JwtVerifier({"test": KEY.public_key()}, issuer=ISS, audience=AUD)
        app = create_api_app(container, verifier, InMemoryTokenBucket(rate_per_s=0.01, burst=burst),
                             LocalObjectStore(tmp_path / "objects"))
        return TestClient(app), container
    return make


def test_requires_bearer_token(make_client):
    client, _ = make_client()
    assert client.post("/v1/cases", json=body(), headers={"Idempotency-Key": "k1"}).status_code == 401


@pytest.mark.parametrize("bad", [dict(exp=-120), dict(aud="other"), dict(key=ec.generate_private_key(ec.SECP256R1())
                                                                        .private_bytes(serialization.Encoding.PEM,
                                                                                       serialization.PrivateFormat.PKCS8,
                                                                                       serialization.NoEncryption()))])
def test_rejects_expired_foreign_or_forged_tokens(make_client, bad):
    client, _ = make_client()
    r = client.post("/v1/cases", json=body(), headers={"Idempotency-Key": "k1", **auth(**bad)})
    assert r.status_code == 401


def test_accepts_with_202_and_is_idempotent(make_client):
    client, _ = make_client()
    h = {"Idempotency-Key": "k1", **auth()}
    a = client.post("/v1/cases", json=body(), headers=h)
    assert a.status_code == 202 and a.headers["Location"].endswith(a.json()["case_id"])
    b = client.post("/v1/cases", json=body(), headers=h)
    assert b.status_code == 202 and b.json()["case_id"] == a.json()["case_id"]
    assert b.headers.get("Idempotent-Replayed") == "true"
    c = client.post("/v1/cases", json=body("policy_change"), headers=h)
    assert c.status_code == 409


def test_missing_idempotency_key_is_rejected(make_client):
    client, _ = make_client()
    assert client.post("/v1/cases", json=body(), headers=auth()).status_code == 422


def test_unknown_fields_are_rejected(make_client):
    client, _ = make_client()
    r = client.post("/v1/cases", json={**body(), "is_safe": True}, headers={"Idempotency-Key": "k", **auth()})
    assert r.status_code == 422


def test_16_storage_outage_returns_503(make_client):
    client, _ = make_client(engine=create_engine("postgresql+psycopg://policyguard@127.0.0.1:1/none"))
    r = client.post("/v1/cases", json=body(), headers={"Idempotency-Key": "k1", **auth()})
    assert r.status_code == 503
    assert client.get("/readyz").status_code == 503 and client.get("/healthz").status_code == 200


def test_rate_limit_returns_429_with_retry_after_per_tenant(make_client):
    client, _ = make_client(burst=2)
    codes = [client.post("/v1/cases", json=body(), headers={"Idempotency-Key": f"k{i}", **auth()}).status_code
             for i in range(3)]
    assert codes == [202, 202, 429]
    r = client.post("/v1/cases", json=body(), headers={"Idempotency-Key": "k9", **auth()})
    assert int(r.headers["Retry-After"]) >= 1
    other = client.post("/v1/cases", json=body(), headers={"Idempotency-Key": "k1",
                                                           **auth(tenant="tenant-b", sub="b_user")})
    assert other.status_code != 429          # another tenant has its own bucket


def test_11_case_is_invisible_to_other_tenants_and_other_payers(make_client):
    client, _ = make_client()
    case_id = client.post("/v1/cases", json=body(), headers={"Idempotency-Key": "k1", **auth()}).json()["case_id"]
    assert client.get(f"/v1/cases/{case_id}", headers=auth()).status_code == 200
    assert client.get(f"/v1/cases/{case_id}", headers=auth(tenant="tenant-b")).status_code == 404
    assert client.get(f"/v1/cases/{case_id}", headers=auth(sub="someone_else")).status_code == 404


def test_reviews_need_reviewer_role_and_if_match(make_client):
    client, container = make_client()
    case_id = client.post("/v1/cases", json=body(), headers={"Idempotency-Key": "k1", **auth()}).json()["case_id"]
    container.worker.relay()
    container.worker.run_once("w1")
    rv = client.get(f"/v1/cases/{case_id}", headers=auth()).json()["row_version"]
    review = {"outcome": "CONFIRMED", "reason": "Bursar confirmed by phone."}
    assert client.post(f"/v1/cases/{case_id}/reviews", json=review,
                       headers={"If-Match": str(rv), **auth()}).status_code == 403
    assert client.post(f"/v1/cases/{case_id}/reviews", json=review,
                       headers={"If-Match": str(rv - 1), **auth(sub="rev", roles=("reviewer",))}).status_code == 409
    assert client.post(f"/v1/cases/{case_id}/reviews", json=review,
                       headers={"If-Match": str(rv), **auth(sub="rev", roles=("reviewer",))}).status_code == 201


def test_policy_approval_requires_mfa(make_client):
    client, container = make_client()
    rv = container.policies.row_version(DISCOVERED_VERSION_ID)
    url = f"/v1/policies/{DISCOVERED_VERSION_ID}/approve"
    assert client.post(url, headers={"If-Match": str(rv), **auth(sub="adm", roles=("policy_admin",))}).status_code == 403
    ok = client.post(url, headers={"If-Match": str(rv), **auth(sub="adm", roles=("policy_admin",), amr=("pwd", "mfa"))})
    assert ok.status_code == 200


PDF_OK = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PDF_JS = b"%PDF-1.4\n1 0 obj<</S /JavaScript /JS (app.alert(1))>>endobj\n%%EOF"


def _upload(client, data: bytes, name="invoice.pdf", declared=None):
    r = client.post("/v1/uploads", json={"filename": name, "content_type": "application/pdf",
                                         "size": declared or len(data)}, headers=auth())
    assert r.status_code == 201, r.text
    up = r.json()
    return up, client.put(up["upload_url"], content=data)


def test_upload_signed_url_quarantine_and_scan(make_client):
    client, _ = make_client()
    up, put = _upload(client, PDF_OK)
    assert put.status_code == 204
    done = client.post(f"/v1/uploads/{up['upload_id']}/complete", headers=auth())
    assert done.status_code == 200 and done.json()["status"] == "CLEAN"


def test_18_malicious_or_oversized_uploads_are_rejected(make_client):
    client, _ = make_client()
    up, _ = _upload(client, PDF_JS)
    done = client.post(f"/v1/uploads/{up['upload_id']}/complete", headers=auth()).json()
    assert done["status"] == "REJECTED" and "active content" in done["reject_reason"]
    too_big = client.post("/v1/uploads", json={"filename": "a.pdf", "content_type": "application/pdf",
                                               "size": 50_000_000}, headers=auth())
    assert too_big.status_code == 422
    up, put = _upload(client, PDF_OK * 3, declared=len(PDF_OK))   # body larger than declared
    assert put.status_code == 413


def test_tampered_or_expired_upload_url_is_refused(make_client):
    client, _ = make_client()
    up, _ = _upload(client, PDF_OK)
    assert client.put(up["upload_url"].replace("sig=", "sig=0"), content=PDF_OK).status_code == 403
    expired = up["upload_url"].split("exp=")[0] + "exp=1&" + up["upload_url"].split("&", 1)[1]
    assert client.put(expired, content=PDF_OK).status_code == 403


def test_other_tenant_cannot_complete_upload(make_client):
    client, _ = make_client()
    up, _ = _upload(client, PDF_OK)
    assert client.post(f"/v1/uploads/{up['upload_id']}/complete", headers=auth(tenant="tenant-b")).status_code == 404


def test_openapi_contract_is_published(make_client):
    client, _ = make_client()
    paths = client.get("/v1/openapi.json").json()["paths"]
    for p in ("/v1/cases", "/v1/cases/{case_id}", "/v1/uploads", "/v1/uploads/{upload_id}/complete",
              "/v1/cases/{case_id}/reviews", "/v1/policies/{version_id}/approve"):
        assert p in paths
