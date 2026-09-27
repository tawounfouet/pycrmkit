"""Internal privacy helpers for public error/log-safe metadata."""

from __future__ import annotations

from collections.abc import Mapping

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = frozenset(
    {
        "address",
        "api_key",
        "authorization",
        "body",
        "credential",
        "credentials",
        "email",
        "external_id",
        "html_body",
        "idempotency_key",
        "message_body",
        "password",
        "phone",
        "postal_address",
        "recipient",
        "sender",
        "secret",
        "signing_secret",
        "text_body",
        "token",
    }
)


def _normalized_key(value: object) -> str:
    return str(value).strip().casefold().replace("-", "_")


def _is_sensitive_key(value: object) -> bool:
    key = _normalized_key(value)
    if key in _SENSITIVE_KEYS:
        return True
    return any(
        key.endswith(f"_{suffix}")
        for suffix in ("api_key", "password", "secret", "token")
    )


def redact_sensitive_value(value: object) -> object:
    """Recursively redact values carried by sensitive mapping keys."""

    if isinstance(value, Mapping):
        return redact_sensitive_mapping(
            {str(key): item for key, item in value.items()}
        )
    if isinstance(value, tuple):
        return tuple(redact_sensitive_value(item) for item in value)
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    return value


def redact_sensitive_mapping(values: Mapping[str, object]) -> dict[str, object]:
    """Return a copy suitable for public errors and privacy-safe diagnostics."""

    result: dict[str, object] = {}
    for key, value in values.items():
        normalized_key = str(key)
        result[normalized_key] = (
            _REDACTED
            if _is_sensitive_key(key)
            else redact_sensitive_value(value)
        )
    return result
