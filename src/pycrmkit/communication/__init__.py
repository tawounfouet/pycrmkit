"""Public Communication-domain API."""

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
    "normalize_communication_address",
]
