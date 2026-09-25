"""Provider-agnostic Communication value objects."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

from pycrmkit.core.references import EntityReference
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError


class CommunicationChannel(StrEnum):
    """Communication channels supported by the current domain foundation."""

    EMAIL = "email"


class CommunicationDirection(StrEnum):
    """Direction of a CRM communication relative to the owning application."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class EmailDeliveryEventType(StrEnum):
    """Normalized email lifecycle event."""

    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    FAILED = "failed"

    @property
    def event_name(self) -> str:
        return f"email.{self.value}"


def _clean_single_line(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split())


def _normalize_optional_single_line(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    normalized = _clean_single_line(value)
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"communication.{field_name}.too_long",
        )
    return normalized


def normalize_communication_address(
    channel: CommunicationChannel | str,
    value: str,
) -> str:
    """Normalize a channel address without applying provider-specific rewriting."""

    parsed_channel = CommunicationChannel(channel)
    cleaned = _clean_single_line(value)
    if not cleaned:
        raise ValidationError(
            "communication address cannot be empty",
            code="communication.address.required",
        )

    if parsed_channel is CommunicationChannel.EMAIL:
        if cleaned.count("@") != 1 or any(character.isspace() for character in cleaned):
            raise ValidationError(
                "email address must contain one @ and no whitespace",
                code="communication.address.email.invalid",
            )
        local, domain = cleaned.rsplit("@", 1)
        if not local or not domain or domain.startswith(".") or domain.endswith("."):
            raise ValidationError(
                "email local-part and domain are required",
                code="communication.address.email.invalid",
            )
        return f"{local.casefold()}@{domain.casefold()}"

    raise ValidationError(
        "unsupported communication channel",
        code="communication.channel.unsupported",
        context={"channel": str(parsed_channel)},
    )


@dataclass(frozen=True, slots=True)
class CommunicationAddress(ValueObject):
    """Provider-neutral destination/source address for one communication channel."""

    channel: CommunicationChannel
    value: str
    normalized: str = field(init=False)

    def __post_init__(self) -> None:
        channel = CommunicationChannel(self.channel)
        cleaned = _clean_single_line(self.value)
        normalized = normalize_communication_address(channel, cleaned)
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "value", cleaned)
        object.__setattr__(self, "normalized", normalized)


@dataclass(frozen=True, slots=True)
class CommunicationRecipient(ValueObject):
    """A communication counterparty optionally linked to a CRM entity."""

    address: CommunicationAddress
    display_name: str | None = None
    reference: EntityReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.address, CommunicationAddress):
            raise ValidationError(
                "recipient address must be a CommunicationAddress",
                code="communication.recipient.address.invalid",
            )
        display_name = _normalize_optional_single_line(
            self.display_name,
            field_name="recipient_display_name",
            max_length=300,
        )
        if self.reference is not None and not isinstance(self.reference, EntityReference):
            raise ValidationError(
                "recipient reference must be an EntityReference",
                code="communication.recipient.reference.invalid",
            )
        object.__setattr__(self, "display_name", display_name)


@dataclass(frozen=True, slots=True)
class CommunicationContent(ValueObject):
    """Provider-agnostic content carried by a communication intent."""

    subject: str | None = None
    text_body: str | None = None
    html_body: str | None = None

    def __post_init__(self) -> None:
        subject = _normalize_optional_single_line(
            self.subject,
            field_name="subject",
            max_length=500,
        )
        text_body = self._normalize_body(self.text_body, field_name="text_body")
        html_body = self._normalize_body(self.html_body, field_name="html_body")
        if text_body is None and html_body is None:
            raise ValidationError(
                "communication content requires a text or HTML body",
                code="communication.content.body.required",
            )
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "text_body", text_body)
        object.__setattr__(self, "html_body", html_body)

    @staticmethod
    def _normalize_body(value: str | None, *, field_name: str) -> str | None:
        if value is None:
            return None
        normalized = unicodedata.normalize("NFKC", value).strip()
        if not normalized:
            return None
        if len(normalized) > 1_000_000:
            raise ValidationError(
                f"{field_name} must be at most 1000000 characters",
                code=f"communication.{field_name}.too_long",
            )
        return normalized
