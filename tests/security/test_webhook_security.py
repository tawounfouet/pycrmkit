"""Webhook signing, replay, secret-rotation, and URL security tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.exceptions import ValidationError
from pycrmkit.webhooks import (
    normalize_webhook_url,
    sign_webhook_payload,
    verify_webhook_signature,
)

NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)
TIMESTAMP = int(NOW.timestamp())
OLD_SECRET = "0123456789abcdef0123456789abcdef"
NEW_SECRET = "fedcba9876543210fedcba9876543210"


def test_signature_freshness_window_rejects_replay_without_changing_legacy_call() -> None:
    payload = b'{"type":"contact.created"}'
    signature = sign_webhook_payload(OLD_SECRET, TIMESTAMP, payload)

    assert verify_webhook_signature(OLD_SECRET, TIMESTAMP, payload, signature)
    assert verify_webhook_signature(
        OLD_SECRET,
        TIMESTAMP,
        payload,
        signature,
        current_timestamp=TIMESTAMP + 300,
        tolerance_seconds=300,
    )
    assert not verify_webhook_signature(
        OLD_SECRET,
        TIMESTAMP,
        payload,
        signature,
        current_timestamp=TIMESTAMP + 301,
        tolerance_seconds=300,
    )


def test_signature_freshness_parameters_are_validated() -> None:
    payload = b"{}"
    signature = sign_webhook_payload(OLD_SECRET, TIMESTAMP, payload)

    with pytest.raises(ValidationError) as timestamp_error:
        verify_webhook_signature(
            OLD_SECRET,
            TIMESTAMP,
            payload,
            signature,
            current_timestamp=-1,
        )
    assert timestamp_error.value.code == "webhook.signing.current_timestamp.invalid"

    with pytest.raises(ValidationError) as tolerance_error:
        verify_webhook_signature(
            OLD_SECRET,
            TIMESTAMP,
            payload,
            signature,
            current_timestamp=TIMESTAMP,
            tolerance_seconds=-1,
        )
    assert tolerance_error.value.code == "webhook.signing.tolerance.invalid"


def test_webhook_secret_rotation_invalidates_old_secret_and_never_audits_value() -> None:
    crm = CRM.memory(
        clock=FixedClock(NOW),
        webhook_auto_delivery=False,
    ).with_context(
        actor_id="security-admin",
        correlation_id="rotate-webhook-secret",
    )
    subscription = crm.webhooks.register(
        url="https://hooks.example.com/security",
        events=("contact.created",),
        signing_secret=OLD_SECRET,
    )

    rotated = crm.webhooks.rotate_secret(
        subscription.id,
        signing_secret=NEW_SECRET,
    )
    assert rotated.signing_secret == NEW_SECRET

    payload = b"security-test"
    old_signature = sign_webhook_payload(OLD_SECRET, TIMESTAMP, payload)
    new_signature = sign_webhook_payload(NEW_SECRET, TIMESTAMP, payload)
    assert not verify_webhook_signature(
        rotated.signing_secret,
        TIMESTAMP,
        payload,
        old_signature,
    )
    assert verify_webhook_signature(
        rotated.signing_secret,
        TIMESTAMP,
        payload,
        new_signature,
    )

    audit = crm.audit.by_correlation("rotate-webhook-secret")
    actions = [entry.action for entry in audit.items]
    assert actions.count("webhook.subscription.secret_rotated") == 1
    audit_text = repr(tuple(entry.changes for entry in audit.items))
    assert OLD_SECRET not in audit_text
    assert NEW_SECRET not in audit_text


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@example.com/hook",
        "https://example.com/hook\r\nX-Injected: yes",
    ],
)
def test_webhook_registration_rejects_credential_or_header_injection_urls(
    url: str,
) -> None:
    with pytest.raises(ValidationError):
        normalize_webhook_url(url)
