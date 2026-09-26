"""SQLAlchemy CommunicationRepository qualification tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationDirection,
    CommunicationIntent,
    CommunicationIntentId,
    CommunicationRecipient,
    CommunicationRecord,
    CommunicationRecordId,
    DeliveryAttempt,
    DeliveryAttemptId,
    EmailDeliveryEvent,
    EmailDeliveryEventId,
    EmailDeliveryEventType,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyCommunicationRepository

NOW = datetime(2026, 9, 26, 9, 45, tzinfo=UTC)


def test_communication_round_trip_and_lookup_semantics(session: Session) -> None:
    repository = SQLAlchemyCommunicationRepository(session)
    contact = EntityReference(
        "contact",
        ContactId(UUID("00000000-0000-4000-8000-000000002001")),
    )
    intent = CommunicationIntent(
        id=CommunicationIntentId(
            UUID("00000000-0000-4000-8000-000000002011")
        ),
        created_at=NOW,
        updated_at=NOW,
        channel=CommunicationChannel.EMAIL,
        recipients=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "buyer@example.com",
                ),
                reference=contact,
            ),
        ),
        content=CommunicationContent(
            subject="Repository qualification",
            text_body="Hello from the SQLAlchemy adapter.",
        ),
        references=(contact,),
        idempotency_key="mail:qualification:1",
    )
    intent.queue(NOW + timedelta(minutes=1))
    repository.save_intent(intent)

    assert repository.get_intent(intent.id) == intent
    assert repository.find_intent_by_idempotency_key(
        "mail:qualification:1"
    ) == intent

    attempt = DeliveryAttempt(
        id=DeliveryAttemptId(
            UUID("00000000-0000-4000-8000-000000002012")
        ),
        created_at=NOW + timedelta(minutes=1),
        updated_at=NOW + timedelta(minutes=1),
        intent_id=intent.id,
        attempt_number=1,
        attempted_at=NOW + timedelta(minutes=1),
        provider="example-provider",
    )
    attempt.accept(
        NOW + timedelta(minutes=2),
        provider_message_id="provider-message-qualification",
    )
    repository.save_attempt(attempt)

    assert repository.get_attempt(attempt.id) == attempt
    assert repository.find_attempt_by_provider_message_id(
        "EXAMPLE-PROVIDER",
        "provider-message-qualification",
    ) == attempt

    record = CommunicationRecord(
        id=CommunicationRecordId(
            UUID("00000000-0000-4000-8000-000000002013")
        ),
        created_at=NOW + timedelta(minutes=2),
        updated_at=NOW + timedelta(minutes=2),
        channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND,
        occurred_at=NOW + timedelta(minutes=2),
        counterparties=(
            CommunicationAddress(
                CommunicationChannel.EMAIL,
                "buyer@example.com",
            ),
        ),
        subject="Repository qualification",
        references=(contact,),
        intent_id=intent.id,
        delivery_attempt_id=attempt.id,
        external_id=attempt.provider_message_id,
        delivery_status=EmailDeliveryEventType.SENT,
        last_delivery_event_at=NOW + timedelta(minutes=2),
        metadata={"provider": "example-provider"},
    )
    repository.save_record(record)

    assert repository.get_record(record.id) == record
    assert repository.find_record_by_intent(intent.id) == record
    assert repository.find_record_by_attempt(attempt.id) == record
    assert repository.list_records_for_reference(
        contact,
        OffsetPageRequest(),
    ).items == (record,)

    event = EmailDeliveryEvent(
        id=EmailDeliveryEventId(
            UUID("00000000-0000-4000-8000-000000002014")
        ),
        intent_id=intent.id,
        event_type=EmailDeliveryEventType.SENT,
        occurred_at=NOW + timedelta(minutes=2),
        recorded_at=NOW + timedelta(minutes=3),
        delivery_attempt_id=attempt.id,
        provider="example-provider",
        provider_message_id=attempt.provider_message_id,
        external_event_id="provider-event-qualification",
        recipient=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "buyer@example.com",
        ),
    )
    repository.append_delivery_event(event)
    repository.append_delivery_event(event)

    assert repository.find_delivery_event_by_external_id(
        "EXAMPLE-PROVIDER",
        "provider-event-qualification",
    ) == event
    assert repository.list_delivery_events_for_intent(
        intent.id,
        OffsetPageRequest(),
    ).items == (event,)
