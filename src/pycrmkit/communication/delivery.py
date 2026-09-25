"""Normalized append-only email delivery history."""

from __future__ import annotations
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pycrmkit.communication.entities import CommunicationIntentId, DeliveryAttemptId
from pycrmkit.communication.value_objects import CommunicationAddress, CommunicationChannel, EmailDeliveryEventType
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.json import freeze_json_mapping
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError

class EmailDeliveryEventId(UUIDId):
    """Identifier for one normalized email lifecycle occurrence."""

def _optional(value: str | None, field_name: str, limit: int) -> str | None:
    if value is None:
        return None
    value = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not value:
        return None
    if len(value) > limit:
        raise ValidationError(f"{field_name} is too long", code=f"communication.delivery_event.{field_name}.too_long")
    return value

@dataclass(frozen=True, slots=True)
class EmailDeliveryEvent:
    id: EmailDeliveryEventId
    intent_id: CommunicationIntentId
    event_type: EmailDeliveryEventType
    occurred_at: datetime
    recorded_at: datetime
    delivery_attempt_id: DeliveryAttemptId | None = None
    provider: str | None = None
    provider_message_id: str | None = None
    external_event_id: str | None = None
    recipient: CommunicationAddress | None = None
    failure_code: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, EmailDeliveryEventId) or not isinstance(self.intent_id, CommunicationIntentId):
            raise ValidationError("invalid delivery event identity", code="communication.delivery_event.identity.invalid")
        event_type = EmailDeliveryEventType(self.event_type)
        provider = _optional(self.provider, "provider", 120)
        message_id = _optional(self.provider_message_id, "provider_message_id", 500)
        external_id = _optional(self.external_event_id, "external_event_id", 500)
        failure = _optional(self.failure_code, "failure_code", 255)
        if self.recipient is not None and self.recipient.channel is not CommunicationChannel.EMAIL:
            raise ValidationError("delivery recipient must be email", code="communication.delivery_event.recipient.invalid")
        if event_type is EmailDeliveryEventType.QUEUED:
            if self.delivery_attempt_id is not None or provider is not None or message_id is not None:
                raise ValidationError("queued event cannot have provider outcome", code="communication.delivery_event.queued.conflict")
        elif self.delivery_attempt_id is None or provider is None:
            raise ValidationError("provider context required", code="communication.delivery_event.provider_context.required")
        if event_type in {EmailDeliveryEventType.DELIVERED, EmailDeliveryEventType.OPENED, EmailDeliveryEventType.CLICKED, EmailDeliveryEventType.BOUNCED} and message_id is None:
            raise ValidationError("provider message id required", code="communication.delivery_event.provider_message_id.required")
        if failure is not None and event_type not in {EmailDeliveryEventType.BOUNCED, EmailDeliveryEventType.FAILED}:
            raise ValidationError("failure code invalid", code="communication.delivery_event.failure_code.invalid")
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "occurred_at", as_utc(self.occurred_at))
        object.__setattr__(self, "recorded_at", as_utc(self.recorded_at))
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "provider_message_id", message_id)
        object.__setattr__(self, "external_event_id", external_id)
        object.__setattr__(self, "failure_code", failure)
        object.__setattr__(self, "metadata", freeze_json_mapping(self.metadata))

    def __deepcopy__(self, memo: dict[int, object]) -> EmailDeliveryEvent:
        del memo
        return self
