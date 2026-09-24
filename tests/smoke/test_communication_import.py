"""Smoke coverage for the provisional 0.4 Communication domain surface."""

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationIntent,
    CommunicationRecord,
    DeliveryAttempt,
)


def test_communication_domain_imports() -> None:
    assert CommunicationAddress.__name__ == "CommunicationAddress"
    assert CommunicationChannel.EMAIL.value == "email"
    assert CommunicationContent.__name__ == "CommunicationContent"
    assert CommunicationIntent.__name__ == "CommunicationIntent"
    assert DeliveryAttempt.__name__ == "DeliveryAttempt"
    assert CommunicationRecord.__name__ == "CommunicationRecord"
