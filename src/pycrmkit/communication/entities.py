"""Communication intent, delivery attempt, and CRM record entities."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pycrmkit.communication.value_objects import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationDirection,
    CommunicationRecipient,
    EmailDeliveryEventType,
)
from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError


class CommunicationIntentId(UUIDId):
    """Strongly typed identifier for a communication intent."""


class DeliveryAttemptId(UUIDId):
    """Strongly typed identifier for one transport attempt."""


class CommunicationRecordId(UUIDId):
    """Strongly typed identifier for a CRM communication record."""


class CommunicationIntentStatus(StrEnum):
    """Lifecycle of a provider-independent outbound communication intent."""

    DRAFT = "draft"
    QUEUED = "queued"
    CANCELLED = "cancelled"


class DeliveryAttemptStatus(StrEnum):
    """Transport-level result before downstream delivery events are known."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    FAILED = "failed"


def _normalize_optional_text(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"communication.{field_name}.too_long",
        )
    return normalized


def _validate_references(references: tuple[EntityReference, ...]) -> None:
    if len(set(references)) != len(references):
        raise ValidationError(
            "communication references must be unique",
            code="communication.reference.duplicate",
        )


def _validate_recipient_channels(
    channel: CommunicationChannel,
    recipients: tuple[CommunicationRecipient, ...],
) -> None:
    if not recipients:
        raise ValidationError(
            "communication requires at least one recipient",
            code="communication.recipient.required",
        )
    identities: set[tuple[CommunicationChannel, str]] = set()
    for recipient in recipients:
        if not isinstance(recipient, CommunicationRecipient):
            raise ValidationError(
                "recipients must be CommunicationRecipient values",
                code="communication.recipient.invalid",
            )
        if recipient.address.channel is not channel:
            raise ValidationError(
                "recipient address channel must match communication channel",
                code="communication.recipient.channel_mismatch",
            )
        identity = (recipient.address.channel, recipient.address.normalized)
        if identity in identities:
            raise ValidationError(
                "communication recipients must be unique by normalized address",
                code="communication.recipient.duplicate",
            )
        identities.add(identity)


@dataclass(eq=False, slots=True)
class CommunicationIntent(TimestampedEntity[CommunicationIntentId]):
    """Provider-independent request to communicate with one or more recipients."""

    channel: CommunicationChannel
    recipients: tuple[CommunicationRecipient, ...]
    content: CommunicationContent
    direction: CommunicationDirection = CommunicationDirection.OUTBOUND
    status: CommunicationIntentStatus = CommunicationIntentStatus.DRAFT
    references: tuple[EntityReference, ...] = ()
    idempotency_key: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    queued_at: datetime | None = None
    cancelled_at: datetime | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.channel = CommunicationChannel(self.channel)
        self.direction = CommunicationDirection(self.direction)
        self.status = CommunicationIntentStatus(self.status)
        self.recipients = tuple(self.recipients)
        self.references = tuple(self.references)
        self.idempotency_key = _normalize_optional_text(
            self.idempotency_key,
            field_name="idempotency_key",
            max_length=255,
        )
        self.metadata = dict(self.metadata)
        self.queued_at = as_utc(self.queued_at) if self.queued_at is not None else None
        self.cancelled_at = (
            as_utc(self.cancelled_at) if self.cancelled_at is not None else None
        )
        if self.direction is not CommunicationDirection.OUTBOUND:
            raise ValidationError(
                "communication intents are outbound in the 0.4 domain foundation",
                code="communication.intent.direction.invalid",
            )
        if not isinstance(self.content, CommunicationContent):
            raise ValidationError(
                "communication intent content must be CommunicationContent",
                code="communication.intent.content.invalid",
            )
        _validate_recipient_channels(self.channel, self.recipients)
        _validate_references(self.references)
        self._validate_lifecycle()

    def queue(self, at: datetime) -> None:
        """Mark a draft intent ready for a provider adapter."""

        instant = self._transition_instant(at)
        if self.status is not CommunicationIntentStatus.DRAFT:
            self._invalid_transition(CommunicationIntentStatus.QUEUED)
        self.status = CommunicationIntentStatus.QUEUED
        self.queued_at = instant
        self.cancelled_at = None
        self.updated_at = instant

    def cancel(self, at: datetime) -> None:
        """Cancel a draft or queued intent before successful provider acceptance."""

        instant = self._transition_instant(at)
        if self.status not in {
            CommunicationIntentStatus.DRAFT,
            CommunicationIntentStatus.QUEUED,
        }:
            self._invalid_transition(CommunicationIntentStatus.CANCELLED)
        self.status = CommunicationIntentStatus.CANCELLED
        self.cancelled_at = instant
        self.updated_at = instant

    def _transition_instant(self, at: datetime) -> datetime:
        instant = as_utc(at)
        if instant < self.created_at:
            raise ValidationError(
                "communication intent transition cannot predate creation",
                code="communication.intent.transition.before_creation",
            )
        return instant

    def _invalid_transition(self, target: CommunicationIntentStatus) -> None:
        raise InvalidStateError(
            f"cannot transition communication intent from {self.status.value} to {target.value}",
            code="communication.intent.transition.invalid",
            context={"from": self.status.value, "to": target.value},
        )

    def _validate_lifecycle(self) -> None:
        if self.queued_at is not None and self.queued_at < self.created_at:
            raise ValidationError(
                "queued_at cannot predate communication intent creation",
                code="communication.intent.queued_at.before_creation",
            )
        if self.cancelled_at is not None and self.cancelled_at < self.created_at:
            raise ValidationError(
                "cancelled_at cannot predate communication intent creation",
                code="communication.intent.cancelled_at.before_creation",
            )
        if self.status is CommunicationIntentStatus.DRAFT:
            if self.queued_at is not None or self.cancelled_at is not None:
                raise ValidationError(
                    "draft communication intents cannot carry lifecycle timestamps",
                    code="communication.intent.lifecycle.draft_conflict",
                )
        elif self.status is CommunicationIntentStatus.QUEUED:
            if self.queued_at is None or self.cancelled_at is not None:
                raise ValidationError(
                    "queued communication intents require queued_at only",
                    code="communication.intent.lifecycle.queued_invalid",
                )
        elif self.status is CommunicationIntentStatus.CANCELLED:
            if self.cancelled_at is None:
                raise ValidationError(
                    "cancelled communication intents require cancelled_at",
                    code="communication.intent.lifecycle.cancelled_at_required",
                )


@dataclass(eq=False, slots=True)
class DeliveryAttempt(TimestampedEntity[DeliveryAttemptId]):
    """One provider transport attempt for a queued communication intent."""

    intent_id: CommunicationIntentId
    attempt_number: int
    attempted_at: datetime
    status: DeliveryAttemptStatus = DeliveryAttemptStatus.PENDING
    provider: str | None = None
    provider_message_id: str | None = None
    failure_code: str | None = None
    completed_at: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        if not isinstance(self.intent_id, CommunicationIntentId):
            raise ValidationError(
                "delivery attempt intent_id must be a CommunicationIntentId",
                code="communication.delivery.intent_id.invalid",
            )
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise ValidationError(
                "delivery attempt number must be a positive integer",
                code="communication.delivery.attempt_number.invalid",
            )
        self.attempted_at = as_utc(self.attempted_at)
        if self.attempted_at < self.created_at:
            raise ValidationError(
                "delivery attempt cannot predate entity creation",
                code="communication.delivery.attempted_at.before_creation",
            )
        self.status = DeliveryAttemptStatus(self.status)
        self.provider = _normalize_optional_text(
            self.provider,
            field_name="provider",
            max_length=120,
        )
        self.provider_message_id = _normalize_optional_text(
            self.provider_message_id,
            field_name="provider_message_id",
            max_length=500,
        )
        self.failure_code = _normalize_optional_text(
            self.failure_code,
            field_name="failure_code",
            max_length=255,
        )
        self.completed_at = (
            as_utc(self.completed_at) if self.completed_at is not None else None
        )
        self.metadata = dict(self.metadata)
        self._validate_lifecycle()

    def accept(self, at: datetime, *, provider_message_id: str | None = None) -> None:
        """Record provider acceptance without claiming final delivery."""

        instant = self._completion_instant(at)
        if self.status is not DeliveryAttemptStatus.PENDING:
            self._invalid_transition(DeliveryAttemptStatus.ACCEPTED)
        self.status = DeliveryAttemptStatus.ACCEPTED
        self.provider_message_id = _normalize_optional_text(
            provider_message_id,
            field_name="provider_message_id",
            max_length=500,
        )
        self.failure_code = None
        self.completed_at = instant
        self.updated_at = instant

    def fail(self, at: datetime, *, failure_code: str | None = None) -> None:
        """Record a failed provider transport attempt."""

        instant = self._completion_instant(at)
        if self.status is not DeliveryAttemptStatus.PENDING:
            self._invalid_transition(DeliveryAttemptStatus.FAILED)
        self.status = DeliveryAttemptStatus.FAILED
        self.failure_code = _normalize_optional_text(
            failure_code,
            field_name="failure_code",
            max_length=255,
        )
        self.provider_message_id = None
        self.completed_at = instant
        self.updated_at = instant

    def _completion_instant(self, at: datetime) -> datetime:
        instant = as_utc(at)
        if instant < self.attempted_at:
            raise ValidationError(
                "delivery completion cannot predate attempted_at",
                code="communication.delivery.completion.before_attempt",
            )
        return instant

    def _invalid_transition(self, target: DeliveryAttemptStatus) -> None:
        raise InvalidStateError(
            f"cannot transition delivery attempt from {self.status.value} to {target.value}",
            code="communication.delivery.transition.invalid",
            context={"from": self.status.value, "to": target.value},
        )

    def _validate_lifecycle(self) -> None:
        if self.completed_at is not None and self.completed_at < self.attempted_at:
            raise ValidationError(
                "completed_at cannot predate attempted_at",
                code="communication.delivery.completed_at.before_attempt",
            )
        if self.status is DeliveryAttemptStatus.PENDING:
            if any((self.completed_at, self.provider_message_id, self.failure_code)):
                raise ValidationError(
                    "pending delivery attempts cannot carry completion outcome",
                    code="communication.delivery.lifecycle.pending_conflict",
                )
        elif self.status is DeliveryAttemptStatus.ACCEPTED:
            if self.completed_at is None or self.failure_code is not None:
                raise ValidationError(
                    "accepted delivery attempts require completed_at and no failure code",
                    code="communication.delivery.lifecycle.accepted_invalid",
                )
        elif self.status is DeliveryAttemptStatus.FAILED:
            if self.completed_at is None or self.provider_message_id is not None:
                raise ValidationError(
                    "failed delivery attempts require completed_at and no provider message id",
                    code="communication.delivery.lifecycle.failed_invalid",
                )


@dataclass(eq=False, slots=True)
class CommunicationRecord(TimestampedEntity[CommunicationRecordId]):
    """CRM history record separated from transport/provider implementation details."""

    channel: CommunicationChannel
    direction: CommunicationDirection
    occurred_at: datetime
    counterparties: tuple[CommunicationAddress, ...]
    subject: str | None = None
    references: tuple[EntityReference, ...] = ()
    intent_id: CommunicationIntentId | None = None
    delivery_attempt_id: DeliveryAttemptId | None = None
    external_id: str | None = None
    delivery_status: EmailDeliveryEventType | None = None
    last_delivery_event_at: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.channel = CommunicationChannel(self.channel)
        self.direction = CommunicationDirection(self.direction)
        self.occurred_at = as_utc(self.occurred_at)
        self.counterparties = tuple(self.counterparties)
        if not self.counterparties:
            raise ValidationError(
                "communication record requires at least one counterparty",
                code="communication.record.counterparty.required",
            )
        normalized_addresses: set[str] = set()
        for address in self.counterparties:
            if not isinstance(address, CommunicationAddress):
                raise ValidationError(
                    "counterparties must be CommunicationAddress values",
                    code="communication.record.counterparty.invalid",
                )
            if address.channel is not self.channel:
                raise ValidationError(
                    "counterparty channel must match communication record channel",
                    code="communication.record.counterparty.channel_mismatch",
                )
            if address.normalized in normalized_addresses:
                raise ValidationError(
                    "communication record counterparties must be unique",
                    code="communication.record.counterparty.duplicate",
                )
            normalized_addresses.add(address.normalized)
        self.subject = _normalize_optional_text(
            self.subject,
            field_name="subject",
            max_length=500,
        )
        self.references = tuple(self.references)
        _validate_references(self.references)
        if self.intent_id is not None and not isinstance(
            self.intent_id, CommunicationIntentId
        ):
            raise ValidationError(
                "record intent_id must be a CommunicationIntentId",
                code="communication.record.intent_id.invalid",
            )
        if self.delivery_attempt_id is not None and not isinstance(
            self.delivery_attempt_id, DeliveryAttemptId
        ):
            raise ValidationError(
                "record delivery_attempt_id must be a DeliveryAttemptId",
                code="communication.record.delivery_attempt_id.invalid",
            )
        self.external_id = _normalize_optional_text(
            self.external_id,
            field_name="external_id",
            max_length=500,
        )
        if self.delivery_status is not None:
            self.delivery_status = EmailDeliveryEventType(self.delivery_status)
            if self.delivery_status is EmailDeliveryEventType.QUEUED:
                raise ValidationError(
                    "communication records cannot use queued as delivery status",
                    code="communication.record.delivery_status.queued_invalid",
                )
        self.last_delivery_event_at = (
            as_utc(self.last_delivery_event_at)
            if self.last_delivery_event_at is not None
            else None
        )
        if (self.delivery_status is None) != (self.last_delivery_event_at is None):
            raise ValidationError(
                "delivery_status and last_delivery_event_at must be set together",
                code="communication.record.delivery_state.incomplete",
            )
        self.metadata = dict(self.metadata)

    def apply_delivery_event(
        self,
        event_type: EmailDeliveryEventType | str,
        *,
        occurred_at: datetime,
        recorded_at: datetime,
    ) -> None:
        parsed = EmailDeliveryEventType(event_type)
        if parsed is EmailDeliveryEventType.QUEUED:
            raise ValidationError(
                "queued events belong to intents",
                code="communication.record.delivery_status.queued_invalid",
            )
        business_time = as_utc(occurred_at)
        ingestion_time = as_utc(recorded_at)
        if self.last_delivery_event_at is None or business_time >= self.last_delivery_event_at:
            self.delivery_status = parsed
            self.last_delivery_event_at = business_time
        if ingestion_time > self.updated_at:
            self.updated_at = ingestion_time
