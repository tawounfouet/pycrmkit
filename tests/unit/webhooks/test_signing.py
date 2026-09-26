"""Webhook HMAC signing tests."""

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.webhooks import (
    sign_webhook_payload,
    verify_webhook_signature,
)


def test_hmac_signature_matches_stable_sha256_vector() -> None:
    secret = "0123456789abcdef0123456789abcdef"
    payload = b'{"type":"contact.created"}'

    signature = sign_webhook_payload(secret, 1760000000, payload)

    assert signature == (
        "v1=dd18d11a47ea5c52641dff6f8ad958b854a9d10c142e555e39b4182668084247"
    )
    assert verify_webhook_signature(secret, 1760000000, payload, signature)


def test_signature_verification_rejects_tampering_and_unknown_prefix() -> None:
    secret = "0123456789abcdef0123456789abcdef"
    payload = b'{"type":"contact.created"}'
    signature = sign_webhook_payload(secret, 1760000000, payload)

    assert not verify_webhook_signature(
        secret,
        1760000000,
        b'{"type":"contact.updated"}',
        signature,
    )
    assert not verify_webhook_signature(secret, 1760000000, payload, "v2=deadbeef")


def test_signing_secret_requires_minimum_entropy_length() -> None:
    with pytest.raises(ValidationError) as error:
        sign_webhook_payload("too-short", 1, b"{}")

    assert error.value.code == "webhook.signing.secret.invalid"
