from __future__ import annotations

import json
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src import security

ISSUER = "https://dashboard.example.test"
AUDIENCE = "https://api.example.test"


def _keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public_jwk.update({"kid": "test-key", "use": "sig", "alg": "RS256"})
    return private, jwt.PyJWK.from_dict(public_jwk)


def _token(private, **overrides):
    now = int(time.time())
    payload = {
        "sub": "user_existing123",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 300,
        "email": "owner@example.test",
        "email_verified": True,
        "role": "owner",
        **overrides,
    }
    return jwt.encode(payload, private, algorithm="RS256", headers={"kid": "test-key"})


@pytest.fixture
def better_auth(monkeypatch):
    monkeypatch.setenv("BETTER_AUTH_ENABLED", "true")
    monkeypatch.setenv("BETTER_AUTH_ISSUER", ISSUER)
    monkeypatch.setenv("BETTER_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("BETTER_AUTH_JWKS_URL", f"{ISSUER}/api/auth/jwks")
    private, pyjwk = _keypair()
    monkeypatch.setattr(
        security,
        "_better_auth_jwk_client",
        lambda _url: SimpleNamespace(get_signing_key_from_jwt=lambda _token: pyjwk),
    )
    return private


def test_better_auth_token_requires_all_verified_claims(better_auth):
    claims = security.verify_better_auth_token(_token(better_auth))
    assert claims is not None
    assert claims["sub"] == "user_existing123"
    assert claims["role"] == "owner"


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.test"},
        {"aud": "https://wrong-audience.test"},
        {"exp": int(time.time()) - 1},
        {"email_verified": False},
        {"role": "superadmin"},
        {"sub": ""},
        {"email": ""},
    ],
)
def test_better_auth_token_fails_closed_for_invalid_claims(better_auth, overrides):
    assert security.verify_better_auth_token(_token(better_auth, **overrides)) is None


def test_better_auth_mode_does_not_fall_through_to_clerk_or_local(monkeypatch):
    monkeypatch.setenv("BETTER_AUTH_ENABLED", "true")
    monkeypatch.setattr(security, "verify_better_auth_token", lambda _token: None)
    monkeypatch.setattr(
        security,
        "_clerk_user_from_token",
        lambda _token: pytest.fail("must not try Clerk in Better Auth mode"),
    )
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda _token: pytest.fail("must not try local auth in Better Auth mode"),
    )
    assert security._user_from_bearer_token("invalid") is None


def test_better_auth_proxy_secret_allows_bearer_resolution(monkeypatch):
    monkeypatch.setenv("BETTER_AUTH_ENABLED", "true")
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "shared-secret")
    assert security._clerk_user_from_proxy_headers(
        {"x-dashboard-proxy-auth": "shared-secret"},
    ) is None


def test_better_auth_mode_preserves_trusted_clerk_proxy_during_staged_cutover(monkeypatch):
    from src import access_store

    monkeypatch.setenv("BETTER_AUTH_ENABLED", "true")
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "shared-secret")
    monkeypatch.setattr(
        access_store,
        "resolve_clerk_member",
        lambda clerk_user_id, email: {
            "id": clerk_user_id,
            "email": email,
            "role": "trader",
            "status": "active",
        },
    )
    user = security._clerk_user_from_proxy_headers(
        {
            "x-dashboard-proxy-auth": "shared-secret",
            "x-clerk-user-id": "user_existing123",
            "x-clerk-user-email": "trader@example.test",
            "x-clerk-session-id": "sess_transition",
        },
    )
    assert user == {
        "id": "user_existing123",
        "email": "trader@example.test",
        "role": "trader",
        "status": "active",
        "session_id": "sess_transition",
        "auth_provider": "clerk",
    }


def test_better_auth_claims_resolve_existing_member_without_privilege_change(monkeypatch):
    monkeypatch.setenv("BETTER_AUTH_ENABLED", "true")
    monkeypatch.setattr(
        security,
        "verify_better_auth_token",
        lambda _token: {
            "sub": "user_existing123",
            "email": "owner@example.test",
            "email_verified": True,
            "role": "admin",
        },
    )
    from src import access_store

    monkeypatch.setattr(
        access_store,
        "resolve_better_auth_member",
        lambda user_id, email: {
            "id": user_id,
            "email": email,
            "role": "owner",
            "status": "active",
        },
    )
    user = security._user_from_bearer_token("valid")
    assert user == {
        "id": "user_existing123",
        "email": "owner@example.test",
        "role": "owner",
        "status": "active",
        "auth_provider": "better-auth",
        "session_id": None,
    }


def test_better_auth_identity_mismatch_fails_without_rebinding_or_account_loss(monkeypatch):
    from copy import deepcopy

    from fastapi import HTTPException

    from src import access_store, account_store

    canonical_id = "user_clerk_canonical"
    store = {
        "members": {
            canonical_id: {
                "id": canonical_id,
                "clerk_user_id": canonical_id,
                "email": "owner@example.test",
                "role": "owner",
                "status": "active",
                "active_account_id": "account_existing",
            },
        },
    }
    accounts = {
        "accounts": {
            "account_existing": {
                "id": "account_existing",
                "user_id": canonical_id,
                "name": "Existing account",
            },
        },
    }
    before_store = deepcopy(store)
    before_accounts = deepcopy(accounts)
    monkeypatch.setattr(access_store, "_load_store", lambda: store)
    monkeypatch.setattr(account_store, "_load_accounts_store", lambda: accounts)

    exact = access_store.resolve_better_auth_member(canonical_id, "OWNER@example.test")
    assert exact["id"] == canonical_id
    assert account_store.list_user_accounts(exact["id"])[0]["id"] == "account_existing"

    with pytest.raises(HTTPException) as exc:
        access_store.resolve_better_auth_member("user_different_better_sub", "owner@example.test")
    assert exc.value.status_code == 403
    assert store == before_store
    assert accounts == before_accounts
