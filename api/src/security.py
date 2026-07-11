"""Authentication and token helpers for the dashboard API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from .clerk_client import clerk_enabled, get_clerk_user_email, verify_clerk_token
from .runtime_data import DATA_DIR

USERS_PATH = DATA_DIR / "users.json"
DEV_SECRET_PATH = DATA_DIR / ".dev_app_secret"
PASSWORD_ITERATIONS = 390_000
TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", str(7 * 24 * 60 * 60)))

_bearer = HTTPBearer(auto_error=False)
BETTER_AUTH_ROLES = {"owner", "admin", "trader", "viewer"}


def better_auth_enabled() -> bool:
    return os.getenv("BETTER_AUTH_ENABLED", "").strip().lower() == "true"


@lru_cache(maxsize=4)
def _better_auth_jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, timeout=10, cache_keys=True)


def verify_better_auth_token(token: str) -> dict[str, Any] | None:
    if not better_auth_enabled() or not token:
        return None
    issuer = os.getenv("BETTER_AUTH_ISSUER", "").strip().rstrip("/")
    audience = os.getenv("BETTER_AUTH_AUDIENCE", "").strip().rstrip("/")
    jwks_url = os.getenv("BETTER_AUTH_JWKS_URL", "").strip()
    if not issuer or not audience or not jwks_url.startswith("https://"):
        return None
    try:
        signing_key = _better_auth_jwk_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except Exception:
        return None
    subject = claims.get("sub")
    email = claims.get("email")
    role = claims.get("role")
    if (
        not isinstance(subject, str)
        or not subject
        or not isinstance(email, str)
        or "@" not in email
        or claims.get("email_verified") is not True
        or role not in BETTER_AUTH_ROLES
    ):
        return None
    return claims


def _better_auth_user_from_token(token: str | None) -> dict[str, Any] | None:
    claims = verify_better_auth_token(token or "")
    if not claims:
        return None
    from .access_store import resolve_better_auth_member

    member = resolve_better_auth_member(str(claims["sub"]), str(claims["email"]).lower())
    if member.get("status") != "active":
        return None
    member["auth_provider"] = "better-auth"
    member["session_id"] = None
    return member


def _user_from_bearer_token(token: str | None) -> dict[str, Any] | None:
    if better_auth_enabled():
        return _better_auth_user_from_token(token)
    clerk_user = _clerk_user_from_token(token)
    if clerk_user is not None:
        return clerk_user
    payload = decode_token(token or "")
    if not payload:
        return None
    return get_user(str(payload.get("sub", "")))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return data if isinstance(data, dict) else default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _load_users_store() -> dict[str, Any]:
    store = _read_json(USERS_PATH, {"users": {}})
    users = store.get("users")
    if not isinstance(users, dict):
        store["users"] = {}
    return store


def _save_users_store(store: dict[str, Any]) -> None:
    _write_json(USERS_PATH, store)


def _app_secret() -> str:
    secret = os.getenv("APP_SECRET_KEY") or os.getenv("AUTH_SECRET")
    if secret:
        return secret

    # Local-only fallback. Production should set APP_SECRET_KEY so auth tokens
    # and encrypted account secrets survive container rebuilds.
    if DEV_SECRET_PATH.exists():
        return DEV_SECRET_PATH.read_text(encoding="utf-8").strip()

    generated = secrets.token_urlsafe(48)
    DEV_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEV_SECRET_PATH.write_text(generated, encoding="utf-8")
    return generated


def app_secret_bytes() -> bytes:
    return _app_secret().encode("utf-8")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            iterations,
        )
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def has_users() -> bool:
    return bool(_load_users_store().get("users"))


def create_user(email: str, password: str) -> dict[str, Any]:
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise ValueError("Enter a valid email address")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")

    store = _load_users_store()
    for user in store["users"].values():
        if user.get("email", "").lower() == clean_email:
            raise ValueError("User already exists")

    user_id = secrets.token_urlsafe(12)
    user = {
        "id": user_id,
        "email": clean_email,
        "password_hash": hash_password(password),
        "active_account_id": None,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    store["users"][user_id] = user
    _save_users_store(store)
    return sanitize_user(user)


def get_user(user_id: str) -> dict[str, Any] | None:
    user = _load_users_store().get("users", {}).get(user_id)
    return dict(user) if isinstance(user, dict) else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    clean_email = email.strip().lower()
    for user in _load_users_store().get("users", {}).values():
        if isinstance(user, dict) and user.get("email", "").lower() == clean_email:
            return dict(user)
    return None


def set_active_account_id(user_id: str, account_id: str | None) -> None:
    store = _load_users_store()
    user = store.get("users", {}).get(user_id)
    if not isinstance(user, dict):
        from .access_store import set_member_active_account_id

        set_member_active_account_id(user_id, account_id)
        return
    user["active_account_id"] = account_id
    user["updated_at"] = _utc_now()
    _save_users_store(store)


def sanitize_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user.get("role") or "owner",
        "status": user.get("status") or "active",
        "auth_provider": user.get("auth_provider") or "local",
        "active_account_id": user.get("active_account_id"),
        "created_at": user.get("created_at"),
    }


def create_token(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    payload_raw = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(app_secret_bytes(), payload_raw.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_raw}.{_b64url_encode(signature)}"


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload_raw, signature_raw = token.split(".", 1)
        expected = hmac.new(app_secret_bytes(), payload_raw.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_decode(signature_raw), expected):
            return None
        payload = json.loads(_b64url_decode(payload_raw))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def authenticate_credentials(email: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_email(email)
    if not user or not verify_password(password, user.get("password_hash", "")):
        return None
    return user


def bootstrap_admin_from_env() -> dict[str, Any] | None:
    if has_users():
        return None
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not email or not password:
        return None
    return create_user(email, password)


def _token_from_authorization_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization[len(prefix) :].strip() or None


def _clerk_user_from_token(token: str | None) -> dict[str, Any] | None:
    if not clerk_enabled() or not token:
        return None

    claims = verify_clerk_token(token)
    if not claims:
        return None

    clerk_user_id = str(claims.get("sub") or "")
    if not clerk_user_id:
        return None

    from .access_store import resolve_clerk_member

    email = _clerk_email_from_claims(claims)
    try:
        member = resolve_clerk_member(clerk_user_id, email)
    except HTTPException as error:
        if email or error.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        email = get_clerk_user_email(clerk_user_id)
        if not email:
            return None
        member = resolve_clerk_member(clerk_user_id, email)
    member["auth_provider"] = "clerk"
    member["session_id"] = claims.get("sid")
    return member


def _clerk_email_from_claims(claims: dict[str, Any]) -> str | None:
    for key in ("email", "email_address", "primary_email_address"):
        value = claims.get(key)
        if isinstance(value, str) and value:
            return value.lower()
    return None


def _clerk_user_from_proxy_headers(headers: Any) -> dict[str, Any] | None:
    proxy_secret = os.getenv("DASHBOARD_PROXY_SECRET")
    supplied_secret = headers.get("x-dashboard-proxy-auth")
    if not supplied_secret:
        return None
    if not proxy_secret or not hmac.compare_digest(str(supplied_secret), proxy_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    clerk_user_id = str(headers.get("x-clerk-user-id") or "")
    if not clerk_user_id:
        if better_auth_enabled():
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    from .access_store import resolve_clerk_member

    email = str(headers.get("x-clerk-user-email") or "").lower() or None
    if not email:
        email = get_clerk_user_email(clerk_user_id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    member = resolve_clerk_member(clerk_user_id, email)
    member["auth_provider"] = "clerk"
    member["session_id"] = headers.get("x-clerk-session-id")
    return member


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    proxy_user = _clerk_user_from_proxy_headers(request.headers)
    if proxy_user is not None:
        return proxy_user

    token = credentials.credentials if credentials else None
    if token is None:
        token = request.cookies.get("sc_session")

    user = _user_from_bearer_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def current_user_for_websocket(websocket: WebSocket) -> dict[str, Any] | None:
    token = websocket.query_params.get("token")
    if not token:
        token = _token_from_authorization_header(websocket.headers.get("authorization"))
    if not token:
        token = websocket.cookies.get("sc_session")
    return _user_from_bearer_token(token)


async def get_requested_account_id(
    request: Request,
    x_account_id: str | None = Header(default=None, alias="X-Account-Id"),
) -> str | None:
    return x_account_id or request.query_params.get("account_id")
