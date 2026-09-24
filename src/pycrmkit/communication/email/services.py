"""Provider-independent email delivery service."""

from __future__ import annotations

from dataclasses import dataclass, field

from pycrmkit.communication.email.messages import EmailMessage
from pycrmkit.communication.email.provider import (
    EmailDeliveryStatus,
    EmailProvider,
    EmailProviderResult,
)
from pycrmkit.communication.entities import (
    CommunicationIntent,
    CommunicationIntentStatus,
    DeliveryAttempt,
    DeliveryAttemptId,
)
from pycrmkit.communication.value_objects import CommunicationAddress, CommunicationChannel
from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import IntegrationError, InvalidStateError


@dataclass(slots=True)
class EmailDeliveryService:
    """Translate a queued email intent into one provider delivery attempt."""

    provider: EmailProvider
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def send(
        self,
        intent: CommunicationIntent,
        *,
        sender: CommunicationAddress,
        attempt_number: int = 1,
    ) -> DeliveryAttempt:
        """Submit a queued intent through the configured provider."""

        if intent.channel is not CommunicationChannel.EMAIL:
            raise InvalidStateError(
                "email delivery requires an email communication intent",
                code="communication.email.intent.channel_required",
                context={"channel": intent.channel.value},
            )
        if intent.status is not CommunicationIntentStatus.QUEUED:
            raise InvalidStateError(
                "email delivery requires a queued communication intent",
                code="communication.email.intent.not_queued",
                context={"status": intent.status.value},
            )

        message = EmailMessage.from_intent(intent, sender=sender)
        attempted_at = self.clock.now()
        result = self.provider.send(message)
        if not isinstance(result, EmailProviderResult):
            raise IntegrationError(
                "email provider returned an invalid result",
                code="communication.email.provider.result.invalid",
                context={"result_type": type(result).__name__},
            )
        completed_at = self.clock.now()

        attempt = DeliveryAttempt(
            id=self.id_factory.new(DeliveryAttemptId),
            created_at=attempted_at,
            updated_at=attempted_at,
            intent_id=intent.id,
            attempt_number=attempt_number,
            attempted_at=attempted_at,
            provider=result.provider,
            metadata=dict(result.provider_metadata),
        )
        if result.status is EmailDeliveryStatus.ACCEPTED:
            attempt.accept(
                completed_at,
                provider_message_id=result.provider_message_id,
            )
        else:
            attempt.fail(
                completed_at,
                failure_code=result.failure_code,
            )
        return attempt
