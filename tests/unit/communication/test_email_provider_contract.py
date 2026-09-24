"""Unit tests for the provider-neutral email contract."""

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
    CommunicationRecipient,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProvider,
    EmailProviderResult,
)
from pycrmkit.exceptions import ValidationError

BASE = datetime(2026, 9, 24, 20, 0, tzinfo=UTC)


class AcceptingProvider:
    def send(self, message: EmailMessage) -> EmailProviderResult:
        return EmailProviderResult(
            provider="fake",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id=f"msg-{message.intent_id}",
        )


def _queued_intent() -> CommunicationIntent:
    intent = CommunicationIntent(
        id=CommunicationIntentId(UUID("00000000-0000-0000-0000-000000000401")),
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
        idempotency_key="mail-401",
    )
    intent.queue(BASE)
    return intent


def test_structural_provider_satisfies_runtime_protocol() -> None:
    assert isinstance(AcceptingProvider(), EmailProvider)


def test_email_message_is_built_from_intent_without_crm_reference_payload() -> None:
    message = EmailMessage.from_intent(
        _queued_intent(),
        sender=CommunicationAddress(CommunicationChannel.EMAIL, "sales@example.com"),
        metadata={"campaign": "proposal"},
    )

    assert message.sender.normalized == "sales@example.com"
    assert message.recipients[0].address.normalized == "buyer@example.com"
    assert message.content.subject == "Proposal"
    assert message.idempotency_key == "mail-401"
    assert message.metadata["campaign"] == "proposal"
    assert not hasattr(message, "references")


def test_provider_result_freezes_json_metadata() -> None:
    metadata = {"response": {"code": 202}}
    result = EmailProviderResult(
        provider=" fake-provider ",
        status=EmailDeliveryStatus.ACCEPTED,
        provider_message_id=" provider-123 ",
        provider_metadata=metadata,
    )
    metadata["response"] = {"code": 500}

    assert result.provider == "fake-provider"
    assert result.provider_message_id == "provider-123"
    assert result.provider_metadata["response"]["code"] == 202


def test_failed_result_rejects_provider_message_id() -> None:
    with pytest.raises(ValidationError) as error:
        EmailProviderResult(
            provider="fake",
            status=EmailDeliveryStatus.FAILED,
            provider_message_id="should-not-exist",
        )

    assert (
        error.value.code
        == "communication.email.provider.result.failed_message_id_conflict"
    )


def test_accepted_result_rejects_failure_code() -> None:
    with pytest.raises(ValidationError) as error:
        EmailProviderResult(
            provider="fake",
            status=EmailDeliveryStatus.ACCEPTED,
            failure_code="smtp.rejected",
        )

    assert (
        error.value.code
        == "communication.email.provider.result.accepted_failure_conflict"
    )
