"""Smoke coverage for the provisional 0.4 email provider contract."""

from pycrmkit.communication import (
    EmailDeliveryService,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProvider,
    EmailProviderResult,
)


def test_email_provider_contract_imports() -> None:
    assert EmailDeliveryService.__name__ == "EmailDeliveryService"
    assert EmailDeliveryStatus.ACCEPTED.value == "accepted"
    assert EmailMessage.__name__ == "EmailMessage"
    assert EmailProvider.__name__ == "EmailProvider"
    assert EmailProviderResult.__name__ == "EmailProviderResult"
