"""Deterministic webhook retry and HTTP response policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class WebhookRetryPolicy:
    """Exponential retry policy with explicit retryable HTTP statuses."""

    max_attempts: int = 5
    base_delay: timedelta = timedelta(seconds=10)
    max_delay: timedelta = timedelta(minutes=10)

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValidationError(
                "max_attempts must be a positive integer",
                code="webhook.retry.max_attempts.invalid",
            )
        if self.base_delay <= timedelta(0):
            raise ValidationError(
                "base_delay must be positive",
                code="webhook.retry.base_delay.invalid",
            )
        if self.max_delay < self.base_delay:
            raise ValidationError(
                "max_delay cannot be shorter than base_delay",
                code="webhook.retry.max_delay.invalid",
            )

    def delay_after(self, attempt_number: int) -> timedelta:
        """Return capped exponential delay after one failed attempt."""

        if type(attempt_number) is not int or attempt_number < 1:
            raise ValidationError(
                "attempt_number must be positive",
                code="webhook.retry.attempt_number.invalid",
            )
        factor = 2 ** (attempt_number - 1)
        return min(self.base_delay * factor, self.max_delay)

    def next_attempt_at(self, failed_at: datetime, attempt_number: int) -> datetime:
        """Return the UTC retry instant after a failed attempt."""

        return as_utc(failed_at) + self.delay_after(attempt_number)

    def should_retry_status(self, status_code: int) -> bool:
        """Retry timeout-like/overload responses and server errors."""

        return status_code in {408, 425, 429} or 500 <= status_code <= 599


__all__ = ["WebhookRetryPolicy"]
