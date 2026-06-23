"""Small Clerk Backend API and JWT helper."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import jwt
from jwt import PyJWKClient

CLERK_API_URL = os.getenv("CLERK_API_URL", "https://api.clerk.com")


def clerk_enabled() -> bool:
    return bool(os.getenv("CLERK_SECRET_KEY"))


def _authorized_parties() -> list[str]:
    raw = os.getenv(
        "CLERK_AUTHORIZED_PARTIES",
        "https://dashboard.kiaparsaprintingmoneymachine.cloud,http://localhost:3000",
    )
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def _jwks_url() -> str:
    if configured := os.getenv("CLERK_JWKS_URL"):
        return configured
    if issuer := os.getenv("CLERK_ISSUER"):
        return issuer.rstrip("/") + "/.well-known/jwks.json"
    return CLERK_API_URL.rstrip("/") + "/v1/jwks"


@lru_cache(maxsize=8)
def _jwk_client(jwks_url: str, use_secret: bool = False) -> PyJWKClient:
    headers = {}
    if use_secret and (secret_key := os.getenv("CLERK_SECRET_KEY")):
        headers["Authorization"] = f"Bearer {secret_key}"
    return PyJWKClient(jwks_url, headers=headers)


def _jwks_urls_for_token(token: str) -> list[tuple[str, bool]]:
    urls: list[tuple[str, bool]] = []

    try:
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
    except Exception:
        unverified_claims = {}

    if configured := os.getenv("CLERK_JWKS_URL"):
        urls.append((configured, False))
    elif issuer := os.getenv("CLERK_ISSUER"):
        urls.append((issuer.rstrip("/") + "/.well-known/jwks.json", False))
    elif token_issuer := str(unverified_claims.get("iss") or "").strip():
        urls.append((token_issuer.rstrip("/") + "/.well-known/jwks.json", False))

    backend_jwks = CLERK_API_URL.rstrip("/") + "/v1/jwks"
    urls.append((backend_jwks, True))

    deduped: list[tuple[str, bool]] = []
    seen = set()
    for url, use_secret in urls:
        key = (url.rstrip("/"), use_secret)
        if key not in seen:
            seen.add(key)
            deduped.append((url, use_secret))
    return deduped


def verify_clerk_token(token: str) -> dict[str, Any] | None:
    if not clerk_enabled() or not token:
        return None

    try:
        jwt_key = os.getenv("CLERK_JWT_KEY", "").strip().replace("\\n", "\n")
        if jwt_key:
            claims = jwt.decode(token, jwt_key, algorithms=["RS256"], options={"verify_aud": False})
        else:
            claims = None
            for jwks_url, use_secret in _jwks_urls_for_token(token):
                try:
                    signing_key = _jwk_client(jwks_url, use_secret).get_signing_key_from_jwt(token)
                    claims = jwt.decode(
                        token,
                        signing_key.key,
                        algorithms=["RS256"],
                        options={"verify_aud": False},
                    )
                    break
                except Exception:
                    continue
            if claims is None:
                return None
    except Exception:
        return None

    issuer = os.getenv("CLERK_ISSUER", "").strip().rstrip("/")
    if issuer and str(claims.get("iss", "")).rstrip("/") != issuer:
        return None

    authorized_parties = _authorized_parties()
    azp = claims.get("azp")
    if azp and str(azp).rstrip("/") not in authorized_parties:
        return None

    if claims.get("sts") == "pending":
        return None

    return claims if isinstance(claims, dict) else None


def _clerk_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    secret_key = os.getenv("CLERK_SECRET_KEY", "").strip()
    if not secret_key:
        raise RuntimeError("CLERK_SECRET_KEY is not configured")

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        CLERK_API_URL.rstrip("/") + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        detail = error.read().decode("utf-8")
        raise RuntimeError(detail or f"Clerk API returned HTTP {error.code}") from error


def get_clerk_user_email(user_id: str) -> str | None:
    try:
        user = _clerk_request("GET", f"/v1/users/{user_id}")
    except Exception:
        return None

    primary_id = user.get("primary_email_address_id")
    email_addresses = user.get("email_addresses", [])
    if isinstance(email_addresses, list):
        for item in email_addresses:
            if isinstance(item, dict) and item.get("id") == primary_id:
                return str(item.get("email_address", "")).lower() or None
        for item in email_addresses:
            if isinstance(item, dict) and item.get("email_address"):
                return str(item["email_address"]).lower()
    return None


def create_clerk_invitation(
    email: str,
    role: str,
    redirect_url: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email_address": email,
        "notify": True,
        "ignore_existing": True,
        "public_metadata": {"signalCopierRole": role},
    }
    if redirect_url:
        payload["redirect_url"] = redirect_url
    return _clerk_request("POST", "/v1/invitations", payload)
