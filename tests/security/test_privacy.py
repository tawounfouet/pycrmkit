"""Security/privacy regression tests for sensitive diagnostics and representations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactEmail, normalize_phone
from pycrmkit.exceptions import ValidationError
from pycrmkit.providers.email import SMTPConfig
from pycrmkit.webhooks import (
    WebhookRequest,
    WebhookSubscription,
    WebhookSubscriptionId,
)

NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)


def test_public_error_serialization_recursively_redacts_sensitive_keys() -> None:
    error = ValidationError(
        "invalid customer input",
        code="security.test",
        context={
            "contact_id": "contact-123",
            "email": "ada@example.com",
            "nested": {
                "api_key": "rk_live_super_secret",
                "phone": "+33612345678",
                "safe": "kept",
            },
        },
    )

    assert error.context["email"] == "ada@example.com"
    assert error.as_dict() == {
        "code": "security.test",
        "message": "invalid customer input",
        "context": {
            "contact_id": "contact-123",
            "email": "[REDACTED]",
            "nested": {
                "api_key": "[REDACTED]",
                "phone": "[REDACTED]",
                "safe": "kept",
            },
        },
    }


def test_contact_validation_errors_do_not_echo_raw_contact_points() -> None:
    raw_email = "Ada Secret <not-an-email>"
    with pytest.raises(ValidationError) as email_error:
        ContactEmail(raw_email)
    assert raw_email not in str(email_error.value.context)
    assert raw_email not in str(email_error.value.as_dict())

    raw_phone = "+33 confidential"
    with pytest.raises(ValidationError) as phone_error:
        normalize_phone(raw_phone)
    assert raw_phone not in str(phone_error.value.context)
    assert raw_phone not in str(phone_error.value.as_dict())


def test_secret_bearing_runtime_objects_have_safe_repr() -> None:
    webhook_secret = "0123456789abcdef0123456789abcdef"
    subscription_url = "https://hooks.example.com/customer?opaque=value"
    subscription = WebhookSubscription(
        id=WebhookSubscriptionId(UUID(int=1)),
        created_at=NOW,
        updated_at=NOW,
        url=subscription_url,
        event_types=("contact.created",),  # type: ignore[arg-type]
        signing_secret=webhook_secret,
    )
    subscription_repr = repr(subscription)
    assert webhook_secret not in subscription_repr
    assert subscription_url not in subscription_repr

    request = WebhookRequest(
        url=subscription_url,
        body=b'{"email":"ada@example.com"}',
        headers={
            "Authorization": "Bearer top-secret",
            "X-PyCRMKit-Signature": "v1=deadbeef",
        },
    )
    request_repr = repr(request)
    assert subscription_url not in request_repr
    assert "ada@example.com" not in request_repr
    assert "Bearer top-secret" not in request_repr

    smtp = SMTPConfig(
        host="smtp.example.com",
        username="mailer",
        password="smtp-super-secret",
    )
    assert "smtp-super-secret" not in repr(smtp)


def test_core_validation_does_not_log_customer_payloads_by_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_email = "private-customer@example com"
    with pytest.raises(ValidationError):
        ContactEmail(raw_email)

    assert raw_email not in caplog.text
