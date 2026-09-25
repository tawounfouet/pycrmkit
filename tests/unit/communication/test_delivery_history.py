from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationDirection,
    CommunicationIntentId,
    CommunicationRecord,
    CommunicationRecordId,
    DeliveryAttemptId,
    EmailDeliveryEvent,
    EmailDeliveryEventId,
    EmailDeliveryEventType,
)
from pycrmkit.exceptions import ValidationError

NOW = datetime(2026, 9, 25, 18, 0, tzinfo=UTC)


def test_record_ignores_out_of_order_state_regression() -> None:
    record = CommunicationRecord(
        id=CommunicationRecordId(
            UUID("00000000-0000-4000-8000-000000000701")
        ),
        created_at=NOW,
        updated_at=NOW,
        channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND,
        occurred_at=NOW,
        counterparties=(
            CommunicationAddress(CommunicationChannel.EMAIL, "a@example.com"),
        ),
        delivery_status=EmailDeliveryEventType.SENT,
        last_delivery_event_at=NOW,
    )

    record.apply_delivery_event(
        EmailDeliveryEventType.OPENED,
        occurred_at=NOW + timedelta(minutes=2),
        recorded_at=NOW + timedelta(minutes=3),
    )
    record.apply_delivery_event(
        EmailDeliveryEventType.DELIVERED,
        occurred_at=NOW + timedelta(minutes=1),
        recorded_at=NOW + timedelta(minutes=4),
    )

    assert record.delivery_status is EmailDeliveryEventType.OPENED
    assert record.updated_at == NOW + timedelta(minutes=4)


def test_downstream_event_requires_provider_message_id() -> None:
    with pytest.raises(ValidationError) as error:
        EmailDeliveryEvent(
            id=EmailDeliveryEventId(
                UUID("00000000-0000-4000-8000-000000000702")
            ),
            intent_id=CommunicationIntentId(
                UUID("00000000-0000-4000-8000-000000000703")
            ),
            event_type=EmailDeliveryEventType.DELIVERED,
            occurred_at=NOW,
            recorded_at=NOW,
            provider="fake",
            delivery_attempt_id=DeliveryAttemptId(
                UUID("00000000-0000-4000-8000-000000000704")
            ),
        )

    assert (
        error.value.code
        == "communication.delivery_event.provider_message_id.required"
    )
