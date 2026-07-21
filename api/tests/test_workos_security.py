from __future__ import annotations

import json
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from src import security

ISSUER = "https://api.workos.com/"
CLIENT_ID = "client_test_123"


def _keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    public_jwk.update({"kid": "test-key", "use": "sig", "alg": "RS256"})
    return private, jwt.PyJWK.from_dict(public_jwk)


def _token(private, **overrides):
    now = int(time.time())
    payload = {
        "sub": "user_existing123",
        "sid": "session_123",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 300,
        **overrides,
    }
    return jwt.encode(payload, private, algorithm="RS256", headers={"kid": "test-key"})


@pytest.fixture
def workos_auth(monkeypatch):
    monkeypatch.setenv("WORKOS_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("WORKOS_ISSUER", ISSUER)
    private, pyjwk = _keypair()
    monkeypatch.setattr(
        security,
        "_workos_jwk_client",
        lambda _url: SimpleNamespace(get_signing_key_from_jwt=lambda _token: pyjwk),
    )
    return private


def test_workos_token_requires_signed_session_claims(workos_auth):
    claims = security.verify_workos_token(_token(workos_auth))
    assert claims is not None
    assert claims["sub"] == "user_existing123"
    assert claims["sid"] == "session_123"


def test_workos_token_uses_default_jwks_when_optional_override_is_blank(
    monkeypatch, workos_auth
):
    seen_urls: list[str] = []
    private, pyjwk = _keypair()
    monkeypatch.setenv("WORKOS_JWKS_URL", "")
    monkeypatch.setattr(
        security,
        "_workos_jwk_client",
        lambda url: (
            seen_urls.append(url)
            or SimpleNamespace(get_signing_key_from_jwt=lambda _token: pyjwk)
        ),
    )

    claims = security.verify_workos_token(_token(private))

    assert claims is not None
    assert seen_urls == [f"https://api.workos.com/sso/jwks/{CLIENT_ID}"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.test/"},
        {"exp": int(time.time()) - 1},
        {"sub": ""},
        {"sid": ""},
    ],
)
def test_workos_token_fails_closed_for_invalid_claims(workos_auth, overrides):
    assert security.verify_workos_token(_token(workos_auth, **overrides)) is None


def test_workos_mode_does_not_fall_through_to_local_tokens(monkeypatch):
    monkeypatch.setenv("WORKOS_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(security, "verify_workos_token", lambda _token: None)
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda _token: pytest.fail("must not try local auth while WorkOS is configured"),
    )
    assert security._user_from_bearer_token("invalid") is None


def test_workos_proxy_headers_resolve_verified_email(monkeypatch):
    from src import access_store

    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "shared-secret")
    monkeypatch.setattr(
        access_store,
        "resolve_workos_member",
        lambda user_id, email: {
            "id": user_id,
            "workos_user_id": user_id,
            "email": email,
            "role": "owner",
            "status": "active",
        },
    )

    user = security._workos_user_from_proxy_headers(
        {
            "x-dashboard-proxy-auth": "shared-secret",
            "x-workos-user-id": "user_existing123",
            "x-workos-user-email": "owner@example.test",
            "x-workos-session-id": "session_123",
        }
    )

    assert user == {
        "id": "user_existing123",
        "workos_user_id": "user_existing123",
        "email": "owner@example.test",
        "role": "owner",
        "status": "active",
        "auth_provider": "workos",
        "session_id": "session_123",
    }
