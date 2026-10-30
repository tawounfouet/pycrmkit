"""LOT-32-003: negative claims for the disposable signed reference host.

These are fixture-host tests; they do NOT certify production JWT/OIDC,
revocation, rotation, trusted IAM, or deployed tenant boundaries.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from host_app import _verified_claims
from starlette.requests import Request

_SIGNING_KEY = b"stable-host-test-only-key-0123456789abcdef0123456789"


def _claims() -> dict[str, object]:
    issued = int(time.time())
    return {
        "iss": "pycrmkit-rc1-host-fixture",
        "aud": "pycrmkit-campaign-host",
        "tenant": "alice",
        "sub": "verified-user",
        "role": "campaign_admin",
        "iat": issued,
        "exp": issued + 600,
    }


def _encode(claims: dict[str, object], *, key: bytes = _SIGNING_KEY) -> str:
    raw = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    mac = hmac.digest(key, raw, hashlib.sha256)
    encoded = [
        base64.urlsafe_b64encode(part).rstrip(b"=").decode()
        for part in (raw, mac)
    ]
    return ".".join(encoded)


def _request(token: str | None) -> Request:
    headers = []
    if token is not None:
        headers.append((b"authorization", ("Bearer " + token).encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_signed_reference_host_accepts_only_valid_short_lived_fixture_claims() -> None:
    result = _verified_claims(_request(_encode(_claims())), _SIGNING_KEY)
    assert result is not None
    assert result["tenant"] == "alice"
    assert result["sub"] == "verified-user"


@pytest.mark.parametrize(
    ("key", "replacement"),
    [
        ("iss", "untrusted-issuer"),
        ("aud", "other-service"),
        ("role", "viewer"),
        ("tenant", "alice/bob"),
        ("sub", ""),
        ("iat", 0),
        ("iat", True),
        ("exp", 0),
        ("exp", True),
    ],
)
def test_signed_reference_host_rejects_invalid_authority_claims(
    key: str, replacement: object,
) -> None:
    claims = _claims()
    claims[key] = replacement
    assert _verified_claims(_request(_encode(claims)), _SIGNING_KEY) is None


def test_signed_reference_host_rejects_future_expired_and_overlong_lifetime() -> None:
    now = int(time.time())
    for modifications in (
        {"iat": now + 120},
        {"exp": now - 1},
        {"exp": now + 901},
    ):
        claims = _claims()
        claims.update(modifications)
        assert _verified_claims(_request(_encode(claims)), _SIGNING_KEY) is None


@pytest.mark.parametrize("token", [None, "", "onepart", "a.b.c", "x" * 2049])
def test_signed_reference_host_rejects_unsigned_or_malformed_bearer(
    token: str | None,
) -> None:
    assert _verified_claims(_request(token), _SIGNING_KEY) is None


def test_signing_key_rotation_invalidates_old_fixture_tokens() -> None:
    old_key = b"revoked-test-signing-key-0123456789abcdef123456"
    token = _encode(_claims(), key=old_key)
    assert _verified_claims(_request(token), old_key) is not None
    assert _verified_claims(_request(token), _SIGNING_KEY) is None
    head, signature = token.split(".")
    changed = "A" if signature[0] != "A" else "B"
    tampered = head + "." + changed + signature[1:]
    assert _verified_claims(_request(tampered), old_key) is None
