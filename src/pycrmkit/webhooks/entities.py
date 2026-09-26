"""Webhook subscription domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.events import EventType
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError
from pycrmkit.webhooks.signing import (
    generate_webhook_secret,
    normalize_webhook_secret,
)


class WebhookSubscriptionId(UUIDId):
    """Strongly typed identifier for a webhook subscription."""


def normalize_webhook_url(value: str) -> str:
    """Validate and normalize a webhook endpoint without performing network I/O."""

    normalized = value.strip()
    if not normalized or len(normalized) > 2048 or any(ch.isspace() for ch in normalized):
        raise ValidationError(
            "webhook url is invalid",
            code="webhook.url.invalid",
        )

    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(
            "webhook url is invalid",
            code="webhook.url.invalid",
        ) from exc

    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValidationError(
            "webhook url must use http or https with a host",
            code="webhook.url.invalid",
        )
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError(
            "webhook url cannot contain embedded credentials",
            code="webhook.url.credentials_forbidden",
        )
    if parsed.fragment:
        raise ValidationError(
            "webhook url cannot contain a fragment",
            code="webhook.url.fragment_forbidden",
        )

    try:
        host = parsed.hostname.encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise ValidationError(
            "webhook hostname is invalid",
            code="webhook.url.invalid",
        ) from exc

    host_part = f"[{host}]" if ":" in host else host
    netloc = f"{host_part}:{port}" if port is not None else host_part
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


@dataclass(eq=False, slots=True)
class WebhookSubscription(TimestampedEntity[WebhookSubscriptionId]):
    """Persistent registration for exact public event-type subscriptions."""

    url: str
    event_types: tuple[EventType, ...]
    signing_secret: str = field(default_factory=generate_webhook_secret, repr=False)
    disabled_at: datetime | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.url = normalize_webhook_url(self.url)
        normalized = tuple(
            sorted(
                {EventType.parse(event_type) for event_type in self.event_types},
                key=str,
            )
        )
        if not normalized:
            raise ValidationError(
                "webhook subscription requires at least one event type",
                code="webhook.events.required",
            )
        self.event_types = normalized
        self.signing_secret = normalize_webhook_secret(self.signing_secret)
        if self.disabled_at is not None:
            self.disabled_at = as_utc(self.disabled_at)
            if self.disabled_at < self.created_at:
                raise ValidationError(
                    "disabled_at cannot be earlier than created_at",
                    code="webhook.disabled_at.invalid",
                )

    @property
    def enabled(self) -> bool:
        """Whether this registration is currently active."""

        return self.disabled_at is None

    def disable(self, at: datetime) -> bool:
        """Disable the subscription idempotently."""

        if self.disabled_at is not None:
            return False
        when = as_utc(at)
        if when < self.created_at:
            raise ValidationError(
                "disabled_at cannot be earlier than created_at",
                code="webhook.disabled_at.invalid",
            )
        self.disabled_at = when
        if when > self.updated_at:
            self.updated_at = when
        return True

    def matches(self, event_type: EventType | str) -> bool:
        """Return whether this active subscription matches one event type."""

        parsed = EventType.parse(event_type)
        return self.enabled and parsed in self.event_types
