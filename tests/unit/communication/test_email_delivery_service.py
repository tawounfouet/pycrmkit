"""Unit tests for provider-independent email delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationIntent,
    CommunicationIntentId,
    CommunicationIntentStatus,
    CommunicationRecipient,
    DeliveryAttemptId,
    DeliveryAttemptStatus,
    EmailDeliveryService,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderResult,
)
from pycrmkit.core.time import FixedClock
from pycrmkit.exceptions import IntegrationError, InvalidStateError

BASE = datetime(2026, 9, 24, 20, 30, tzinfo=UTC)


class FixedIdFactory:
    def new(self, id_type: type[DeliveryAttemptId]) -> DeliveryAttemptId:
        return id_type(UUID("00000000-0000-0000-0000-000000000499"))


class RecordingProvider:
    def __init__(self, result: EmailProviderResult) -> None:
        self.result = result
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> EmailProviderResult:
        self.messages.append(message)
        return self.result


class InvalidProvider:
    def send(self, message: EmailMessage) -> object:
        del message
        return object()


def _intent(*, queued: bool = True) -> CommunicationIntent:
    intent = CommunicationIntent(
        id=CommunicationIntentId(UUID("00000000-0000-0000-0000-000000000402")),
        created_at=BASE,
        updated_at=BASE,
        channel=CommunicationChannel.EMAIL,
        recipients=(
            CommunicationRecipient(
                CommunicationAddress(CommunicationChannel.EMAIL, "buyer@example.com")
            ),
        ),
        content=CommunicationContent(
            subject="Proposal",
            text_body="Hello",
        ),
        idempotency_key="mail-402",
    )
    if queued:
        intent.queue(BASE)
    return intent


def test_service_maps_provider_acceptance_to_delivery_attempt() -> None:
    provider = RecordingProvider(
        EmailProviderResult(
            provider="fake",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="msg-402",
            provider_metadata={"request_id": "req-1"},
        )
    )
    service = EmailDeliveryService(
        provider=provider,
        id_factory=FixedIdFactory(),
        clock=FixedClock(BASE),
    )

    attempt = service.send(
        _intent(),
        sender=CommunicationAddress(CommunicationChannel.EMAIL, "sales@example.com"),
    )

    assert attempt.id == DeliveryAttemptId(
        UUID("00000000-0000-0000-0000-000000000499")
    )
    assert attempt.status is DeliveryAttemptStatus.ACCEPTED
    assert attempt.provider == "fake"
    assert attempt.provider_message_id == "msg-402"
    assert attempt.metadata == {"request_id": "req-1"}
    assert provider.messages[0].idempotency_key == "mail-402"


def test_service_maps_provider_failure_to_delivery_attempt() -> None:
    provider = RecordingProvider(
        EmailProviderResult(
            provider="fake",
            status=EmailDeliveryStatus.FAILED,
            failure_code="smtp.rejected",
            provider_metadata={"smtp_code": 550},
        )
    )
    service = EmailDeliveryService(
        provider=provider,
        id_factory=FixedIdFactory(),
        clock=FixedClock(BASE),
    )

    attempt = service.send(
        _intent(),
        sender=CommunicationAddress(CommunicationChannel.EMAIL, "sales@example.com"),
        attempt_number=2,
    )

    assert attempt.status is DeliveryAttemptStatus.FAILED
    assert attempt.attempt_number == 2
    assert attempt.failure_code == "smtp.rejected"
    assert attempt.metadata == {"smtp_code": 550}


def test_service_rejects_draft_intent_before_calling_provider() -> None:
    provider = RecordingProvider(
        EmailProviderResult(
            provider="fake",
            status=EmailDeliveryStatus.ACCEPTED,
        )
    )
    service = EmailDeliveryService(
        provider=provider,
        id_factory=FixedIdFactory(),
        clock=FixedClock(BASE),
    )

    with pytest.raises(InvalidStateError) as error:
        service.send(
            _intent(queued=False),
            sender=CommunicationAddress(
                CommunicationChannel.EMAIL,
                "sales@example.com",
            ),
        )

    assert error.value.code == "communication.email.intent.not_queued"
    assert provider.messages == []


def test_service_rejects_provider_contract_violation() -> None:
    service = EmailDeliveryService(
        provider=InvalidProvider(),  # type: ignore[arg-type]
        id_factory=FixedIdFactory(),
        clock=FixedClock(BASE),
    )

    with pytest.raises(IntegrationError) as error:
        service.send(
            _intent(),
            sender=CommunicationAddress(
                CommunicationChannel.EMAIL,
                "sales@example.com",
            ),
        )

    assert error.value.code == "communication.email.provider.result.invalid"


def test_queued_intent_remains_queued_after_transport_attempt() -> None:
    intent = _intent()
    provider = RecordingProvider(
        EmailProviderResult(
            provider="fake",
            status=EmailDeliveryStatus.ACCEPTED,
        )
    )
    service = EmailDeliveryService(
        provider=provider,
        id_factory=FixedIdFactory(),
        clock=FixedClock(BASE),
    )

    service.send(
        intent,
        sender=CommunicationAddress(CommunicationChannel.EMAIL, "sales@example.com"),
    )

    assert intent.status is CommunicationIntentStatus.QUEUED
