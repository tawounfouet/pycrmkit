"""Unit tests for Communication domain entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.communication.entities import (
    CommunicationIntent,
    CommunicationIntentId,
    CommunicationIntentStatus,
    CommunicationRecord,
    CommunicationRecordId,
    DeliveryAttempt,
    DeliveryAttemptId,
    DeliveryAttemptStatus,
)
from pycrmkit.communication.value_objects import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationDirection,
    CommunicationRecipient,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import InvalidStateError, ValidationError

BASE = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)


def _intent() -> CommunicationIntent:
    contact_id = ContactId(UUID("00000000-0000-0000-0000-000000000021"))
    return CommunicationIntent(
        id=CommunicationIntentId(UUID("00000000-0000-0000-0000-000000000101")),
        created_at=BASE,
        updated_at=BASE,
        channel=CommunicationChannel.EMAIL,
        recipients=(
            CommunicationRecipient(
                CommunicationAddress(CommunicationChannel.EMAIL, "buyer@example.com"),
                reference=EntityReference("contact", contact_id),
            ),
        ),
        content=CommunicationContent(
            subject="Proposal follow-up",
            text_body="Hello, here is the next step.",
        ),
        references=(EntityReference("contact", contact_id),),
        idempotency_key=" crm:mail:001 ",
    )


def test_intent_is_provider_independent_and_queues_explicitly() -> None:
    intent = _intent()

    assert intent.status is CommunicationIntentStatus.DRAFT
    assert intent.idempotency_key == "crm:mail:001"
    assert not hasattr(intent, "provider")

    intent.queue(BASE + timedelta(minutes=1))

    assert intent.status is CommunicationIntentStatus.QUEUED
    assert intent.queued_at == BASE + timedelta(minutes=1)
    assert intent.updated_at == BASE + timedelta(minutes=1)


def test_queued_intent_can_be_cancelled_but_not_requeued() -> None:
    intent = _intent()
    intent.queue(BASE + timedelta(minutes=1))
    intent.cancel(BASE + timedelta(minutes=2))

    assert intent.status is CommunicationIntentStatus.CANCELLED
    assert intent.cancelled_at == BASE + timedelta(minutes=2)

    with pytest.raises(InvalidStateError) as error:
        intent.queue(BASE + timedelta(minutes=3))

    assert error.value.code == "communication.intent.transition.invalid"


def test_intent_rejects_duplicate_normalized_recipients() -> None:
    address_a = CommunicationAddress(CommunicationChannel.EMAIL, "A@Example.com")
    address_b = CommunicationAddress(CommunicationChannel.EMAIL, "a@example.COM")

    with pytest.raises(ValidationError) as error:
        CommunicationIntent(
            id=CommunicationIntentId(UUID("00000000-0000-0000-0000-000000000102")),
            created_at=BASE,
            updated_at=BASE,
            channel=CommunicationChannel.EMAIL,
            recipients=(
                CommunicationRecipient(address_a),
                CommunicationRecipient(address_b),
            ),
            content=CommunicationContent(text_body="Hello"),
        )

    assert error.value.code == "communication.recipient.duplicate"


def test_intent_is_outbound_only_at_this_foundation_stage() -> None:
    with pytest.raises(ValidationError) as error:
        CommunicationIntent(
            id=CommunicationIntentId(UUID("00000000-0000-0000-0000-000000000103")),
            created_at=BASE,
            updated_at=BASE,
            channel=CommunicationChannel.EMAIL,
            direction=CommunicationDirection.INBOUND,
            recipients=(
                CommunicationRecipient(
                    CommunicationAddress(CommunicationChannel.EMAIL, "sender@example.com")
                ),
            ),
            content=CommunicationContent(text_body="Imported inbound body"),
        )

    assert error.value.code == "communication.intent.direction.invalid"


def test_delivery_attempt_tracks_transport_acceptance_not_final_delivery() -> None:
    intent = _intent()
    intent.queue(BASE + timedelta(minutes=1))
    attempt = DeliveryAttempt(
        id=DeliveryAttemptId(UUID("00000000-0000-0000-0000-000000000201")),
        created_at=BASE + timedelta(minutes=1),
        updated_at=BASE + timedelta(minutes=1),
        intent_id=intent.id,
        attempt_number=1,
        attempted_at=BASE + timedelta(minutes=1),
        provider="example-provider",
    )

    attempt.accept(
        BASE + timedelta(minutes=2),
        provider_message_id="provider-message-123",
    )

    assert attempt.status is DeliveryAttemptStatus.ACCEPTED
    assert attempt.provider_message_id == "provider-message-123"
    assert attempt.completed_at == BASE + timedelta(minutes=2)


def test_delivery_attempt_failure_is_terminal() -> None:
    attempt = DeliveryAttempt(
        id=DeliveryAttemptId(UUID("00000000-0000-0000-0000-000000000202")),
        created_at=BASE,
        updated_at=BASE,
        intent_id=CommunicationIntentId(
            UUID("00000000-0000-0000-0000-000000000104")
        ),
        attempt_number=1,
        attempted_at=BASE,
    )
    attempt.fail(BASE + timedelta(seconds=1), failure_code="transport.timeout")

    assert attempt.status is DeliveryAttemptStatus.FAILED
    assert attempt.failure_code == "transport.timeout"

    with pytest.raises(InvalidStateError):
        attempt.accept(BASE + timedelta(seconds=2))


def test_communication_record_is_a_crm_history_record_without_message_body() -> None:
    record = CommunicationRecord(
        id=CommunicationRecordId(UUID("00000000-0000-0000-0000-000000000301")),
        created_at=BASE,
        updated_at=BASE,
        channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND,
        occurred_at=BASE - timedelta(days=2),
        counterparties=(
            CommunicationAddress(CommunicationChannel.EMAIL, "buyer@example.com"),
        ),
        subject="Proposal follow-up",
        intent_id=CommunicationIntentId(
            UUID("00000000-0000-0000-0000-000000000105")
        ),
        delivery_attempt_id=DeliveryAttemptId(
            UUID("00000000-0000-0000-0000-000000000203")
        ),
    )

    assert record.occurred_at == BASE - timedelta(days=2)
    assert record.subject == "Proposal follow-up"
    assert not hasattr(record, "text_body")
    assert not hasattr(record, "html_body")


def test_lifecycle_timestamps_are_timezone_aware() -> None:
    intent = _intent()

    with pytest.raises(ValueError):
        intent.queue(datetime(2026, 9, 24, 10, 1))
