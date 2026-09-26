"""Webhook retry/backoff policy tests."""

from datetime import UTC, datetime, timedelta

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.webhooks import WebhookRetryPolicy

NOW = datetime(2026, 9, 26, 9, 0, tzinfo=UTC)


def test_retry_policy_uses_capped_exponential_backoff() -> None:
    policy = WebhookRetryPolicy(
        max_attempts=5,
        base_delay=timedelta(seconds=10),
        max_delay=timedelta(seconds=25),
    )

    assert policy.delay_after(1) == timedelta(seconds=10)
    assert policy.delay_after(2) == timedelta(seconds=20)
    assert policy.delay_after(3) == timedelta(seconds=25)
    assert policy.next_attempt_at(NOW, 2) == NOW + timedelta(seconds=20)


def test_retryable_http_status_policy_is_explicit() -> None:
    policy = WebhookRetryPolicy()

    for status in (408, 425, 429, 500, 503, 599):
        assert policy.should_retry_status(status)

    for status in (200, 301, 400, 401, 404, 422):
        assert not policy.should_retry_status(status)


def test_retry_policy_rejects_invalid_configuration() -> None:
    with pytest.raises(ValidationError):
        WebhookRetryPolicy(max_attempts=0)
    with pytest.raises(ValidationError):
        WebhookRetryPolicy(base_delay=timedelta(0))
