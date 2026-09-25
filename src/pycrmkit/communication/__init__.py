"""Public Communication-domain API."""

from pycrmkit.communication.delivery import EmailDeliveryEvent, EmailDeliveryEventId
from pycrmkit.communication.email import (
    EmailDeliveryService,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProvider,
    EmailProviderResult,
    EmailTemplate,
    TemplateRenderer,
)
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
    EmailDeliveryEventType,
    normalize_communication_address,
)

__all__ = [
    "CommunicationAddress",
    "CommunicationChannel",
    "CommunicationContent",
    "CommunicationDirection",
    "CommunicationIntent",
    "CommunicationIntentId",
    "CommunicationIntentStatus",
    "CommunicationRecipient",
    "CommunicationRecord",
    "CommunicationRecordId",
    "DeliveryAttempt",
    "DeliveryAttemptId",
    "DeliveryAttemptStatus",
    "EmailDeliveryEvent",
    "EmailDeliveryEventId",
    "EmailDeliveryEventType",
    "EmailDeliveryService",
    "EmailDeliveryStatus",
    "EmailMessage",
    "EmailProvider",
    "EmailProviderResult",
    "EmailTemplate",
    "TemplateRenderer",
    "normalize_communication_address",
]
