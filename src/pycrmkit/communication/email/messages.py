"""Provider-neutral email message DTOs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pycrmkit.communication.entities import CommunicationIntent, CommunicationIntentId
from pycrmkit.communication.value_objects import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationRecipient,
)
from pycrmkit.core.json import freeze_json_mapping
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class EmailMessage(ValueObject):
    """Immutable email request passed to an EmailProvider implementation."""

    intent_id: CommunicationIntentId
    sender: CommunicationAddress
    recipients: tuple[CommunicationRecipient, ...]
    content: CommunicationContent
    idempotency_key: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, CommunicationIntentId):
            raise ValidationError(
                "email message intent_id must be a CommunicationIntentId",
                code="communication.email.message.intent_id.invalid",
            )
        if not isinstance(self.sender, CommunicationAddress):
            raise ValidationError(
                "email message sender must be a CommunicationAddress",
                code="communication.email.message.sender.invalid",
            )
        if self.sender.channel is not CommunicationChannel.EMAIL:
            raise ValidationError(
                "email message sender must use the email channel",
                code="communication.email.message.sender.channel_invalid",
            )
        recipients = tuple(self.recipients)
        if not recipients:
            raise ValidationError(
                "email message requires at least one recipient",
                code="communication.email.message.recipient.required",
            )
        normalized: set[str] = set()
        for recipient in recipients:
            if not isinstance(recipient, CommunicationRecipient):
                raise ValidationError(
                    "email recipients must be CommunicationRecipient values",
                    code="communication.email.message.recipient.invalid",
                )
            if recipient.address.channel is not CommunicationChannel.EMAIL:
                raise ValidationError(
                    "email recipients must use the email channel",
                    code="communication.email.message.recipient.channel_invalid",
                )
            if recipient.address.normalized in normalized:
                raise ValidationError(
                    "email recipients must be unique by normalized address",
                    code="communication.email.message.recipient.duplicate",
                )
            normalized.add(recipient.address.normalized)
        if not isinstance(self.content, CommunicationContent):
            raise ValidationError(
                "email message content must be CommunicationContent",
                code="communication.email.message.content.invalid",
            )
        idempotency_key = self.idempotency_key
        if idempotency_key is not None:
            idempotency_key = " ".join(idempotency_key.strip().split()) or None
            if idempotency_key is not None and len(idempotency_key) > 255:
                raise ValidationError(
                    "email idempotency_key must be at most 255 characters",
                    code="communication.email.message.idempotency_key.too_long",
                )
        object.__setattr__(self, "recipients", recipients)
        object.__setattr__(self, "idempotency_key", idempotency_key)
        object.__setattr__(self, "metadata", freeze_json_mapping(self.metadata))

    @classmethod
    def from_intent(
        cls,
        intent: CommunicationIntent,
        *,
        sender: CommunicationAddress,
        metadata: Mapping[str, object] | None = None,
    ) -> EmailMessage:
        """Build the provider DTO without exposing CRM references to the provider."""

        if intent.channel is not CommunicationChannel.EMAIL:
            raise ValidationError(
                "only email communication intents can become EmailMessage values",
                code="communication.email.intent.channel_invalid",
            )
        return cls(
            intent_id=intent.id,
            sender=sender,
            recipients=intent.recipients,
            content=intent.content,
            idempotency_key=intent.idempotency_key,
            metadata=metadata or {},
        )
