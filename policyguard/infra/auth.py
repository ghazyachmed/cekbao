"""JWT bearer verification for /v1 (OIDC-compatible access tokens, ES256 only).

The local deployment uses a development JWKS in .local/ (git-ignored). A real OIDC provider plugs in by
loading its JWKS; that integration is BLOCKED until an identity provider is chosen (see docs).
"""
from __future__ import annotations

import json
from pathlib import Path

import jwt
from jwt.algorithms import ECAlgorithm

from policyguard.application.errors import PolicyGuardError
from policyguard.application.service import Actor

MFA_METHODS = {"mfa", "otp", "hwk", "swk", "fido"}


class Unauthorized(PolicyGuardError):
    status, code = 401, "unauthorized"


class JwtVerifier:
    def __init__(self, keys: dict, issuer: str, audience: str, leeway_s: int = 30):
        self.keys, self.issuer, self.audience, self.leeway = keys, issuer, audience, leeway_s

    @classmethod
    def from_jwks_file(cls, path: Path, issuer: str, audience: str) -> JwtVerifier:
        data = json.loads(path.read_text())
        keys = {k["kid"]: ECAlgorithm.from_jwk(json.dumps(k)) for k in data["keys"]}
        return cls(keys, issuer, audience)

    def actor(self, authorization: str | None) -> Actor:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise Unauthorized("Bearer token required.")
        raw = authorization.split(" ", 1)[1].strip()
        try:
            kid = jwt.get_unverified_header(raw).get("kid")
            key = self.keys.get(kid)
            if key is None:
                raise Unauthorized("Unknown signing key.")
            claims = jwt.decode(raw, key, algorithms=["ES256"], audience=self.audience, issuer=self.issuer,
                                leeway=self.leeway, options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        except jwt.PyJWTError:
            raise Unauthorized("Invalid or expired token.") from None
        tenant = claims.get("tid")
        if not isinstance(tenant, str) or not tenant:
            raise Unauthorized("Token has no tenant.")
        roles = frozenset(r for r in claims.get("roles", []) if isinstance(r, str))
        return Actor(str(claims["sub"]), tenant, roles, mfa=bool(MFA_METHODS & set(claims.get("amr", []))))
