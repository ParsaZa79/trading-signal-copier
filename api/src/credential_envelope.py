"""Versioned, cryptographically validated envelopes for broker credentials."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken

from src.security import app_secret_bytes

_ENVELOPE_PREFIX = b"fernet:v1:"
_MAX_CREDENTIAL_KEYS = 64
_MAX_KEY_BYTES = 128
_MAX_VALUE_BYTES = 4096
_MAX_PAYLOAD_BYTES = 32_768


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(app_secret_bytes()).digest())
    return Fernet(key)


def _normalize_credentials(credentials: Mapping[str, str]) -> dict[str, str]:
    if len(credentials) > _MAX_CREDENTIAL_KEYS:
        raise ValueError("credential payload has too many fields")

    normalized: dict[str, str] = {}
    for raw_key, raw_value in credentials.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise ValueError("credential payload keys and values must be strings")
        key = raw_key.strip()
        if not key or len(key.encode("utf-8")) > _MAX_KEY_BYTES:
            raise ValueError("credential payload contains an invalid key")
        if len(raw_value.encode("utf-8")) > _MAX_VALUE_BYTES:
            raise ValueError("credential payload contains an oversized value")
        normalized[key] = raw_value
    return normalized


def seal_credentials(credentials: Mapping[str, str]) -> bytes:
    """Seal a bounded credential mapping into a versioned Fernet envelope."""
    normalized = _normalize_credentials(credentials)
    payload = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    if len(payload) > _MAX_PAYLOAD_BYTES:
        raise ValueError("credential payload exceeds size limit")
    return _ENVELOPE_PREFIX + _fernet().encrypt(payload)


def unseal_credentials(envelope: bytes) -> dict[str, str]:
    """Authenticate, decrypt, and validate a versioned credential envelope."""
    if not isinstance(envelope, bytes) or not envelope.startswith(_ENVELOPE_PREFIX):
        raise ValueError("credentials must be a valid encrypted envelope")
    token = envelope.removeprefix(_ENVELOPE_PREFIX)
    if not token:
        raise ValueError("credentials must be a valid encrypted envelope")
    try:
        payload = _fernet().decrypt(token)
    except (InvalidToken, ValueError, TypeError) as error:
        raise ValueError("credentials must be a valid encrypted envelope") from error
    if len(payload) > _MAX_PAYLOAD_BYTES:
        raise ValueError("credential payload exceeds size limit")
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("credential envelope payload is invalid") from error
    if not isinstance(decoded, dict):
        raise ValueError("credential envelope payload must be an object")
    return _normalize_credentials(decoded)


def validate_credentials_envelope(envelope: bytes) -> None:
    """Reject malformed, unauthenticated, or schema-invalid credential envelopes."""
    unseal_credentials(envelope)
