"""Webhook subscription entity validation tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.events import EventType
from pycrmkit.exceptions import ValidationError
from pycrmkit.webhooks import (
    WebhookSubscription,
    WebhookSubscriptionId,
    normalize_webhook_url,
)

NOW = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


def test_webhook_url_normalizes_scheme_host_and_root_path() -> None:
    assert (
        normalize_webhook_url(" HTTPS://Hooks.Example.COM ")
        == "https://hooks.example.com/"
    )


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("ftp://example.com/hook", "webhook.url.invalid"),
        ("https://user:secret@example.com/hook", "webhook.url.credentials_forbidden"),
        ("https://example.com/hook#fragment", "webhook.url.fragment_forbidden"),
        ("https:///missing-host", "webhook.url.invalid"),
    ],
)
def test_webhook_url_rejects_invalid_or_unsafe_registration_forms(
    url: str,
    code: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        normalize_webhook_url(url)
    assert error.value.code == code


def test_subscription_deduplicates_event_types_and_matches_only_while_enabled() -> None:
    subscription = WebhookSubscription(
        id=WebhookSubscriptionId(UUID(int=1)),
        created_at=NOW,
        updated_at=NOW,
        url="https://hooks.example.com/events",
        event_types=(
            EventType.parse("opportunity.won"),
            EventType.parse("contact.created"),
            EventType.parse("contact.created"),
        ),
    )

    assert tuple(map(str, subscription.event_types)) == (
        "contact.created",
        "opportunity.won",
    )
    assert subscription.matches("contact.created") is True

    assert subscription.disable(NOW) is True
    assert subscription.disable(NOW) is False
    assert subscription.matches("contact.created") is False


def test_subscription_requires_at_least_one_event_type() -> None:
    with pytest.raises(ValidationError) as error:
        WebhookSubscription(
            id=WebhookSubscriptionId(UUID(int=2)),
            created_at=NOW,
            updated_at=NOW,
            url="https://hooks.example.com/events",
            event_types=(),
        )
    assert error.value.code == "webhook.events.required"
