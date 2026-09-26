"""HMAC signing helpers for webhook payloads."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from pycrmkit.exceptions import ValidationError

SIGNATURE_PREFIX = "v1="


def generate_webhook_secret() -> str:
    """Generate a high-entropy URL-safe signing secret."""

    return secrets.token_urlsafe(32)


def normalize_webhook_secret(secret: str) -> str:
    """Validate one text signing secret without exposing it in errors."""

    if not isinstance(secret, str):
        raise ValidationError(
            "webhook signing secret must be text",
            code="webhook.signing.secret.invalid",
        )
    value = secret.strip()
    encoded = value.encode("utf-8")
    if len(encoded) < 16 or len(encoded) > 512:
        raise ValidationError(
            "webhook signing secret length is invalid",
            code="webhook.signing.secret.invalid",
        )
    return value


def _signed_bytes(timestamp: int, payload: bytes) -> bytes:
    if type(timestamp) is not int or timestamp < 0:
        raise ValidationError(
            "webhook timestamp must be a non-negative integer",
            code="webhook.signing.timestamp.invalid",
        )
    return str(timestamp).encode("ascii") + b"." + payload


def sign_webhook_payload(secret: str, timestamp: int, payload: bytes) -> str:
    """Return a versioned HMAC-SHA256 signature."""

    key = normalize_webhook_secret(secret).encode("utf-8")
    digest = hmac.new(key, _signed_bytes(timestamp, payload), hashlib.sha256).hexdigest()
    return SIGNATURE_PREFIX + digest


def verify_webhook_signature(
    secret: str,
    timestamp: int,
    payload: bytes,
    signature: str,
) -> bool:
    """Verify a versioned webhook signature using constant-time comparison."""

    if not isinstance(signature, str) or not signature.startswith(SIGNATURE_PREFIX):
        return False
    expected = sign_webhook_payload(secret, timestamp, payload)
    return hmac.compare_digest(expected, signature)


__all__ = [
    "SIGNATURE_PREFIX",
    "generate_webhook_secret",
    "normalize_webhook_secret",
    "sign_webhook_payload",
    "verify_webhook_signature",
]
