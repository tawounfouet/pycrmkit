"""Unit tests for Communication value objects."""

from __future__ import annotations

from uuid import UUID

import pytest

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationRecipient,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ValidationError


def test_email_address_normalizes_for_comparison() -> None:
    address = CommunicationAddress(
        channel=CommunicationChannel.EMAIL,
        value="  Thomas.Example@Example.COM  ",
    )

    assert address.value == "Thomas.Example@Example.COM"
    assert address.normalized == "thomas.example@example.com"


@pytest.mark.parametrize(
    "value",
    ["", "missing-at.example.com", "a@@example.com", "a @example.com"],
)
def test_email_address_rejects_invalid_shape(value: str) -> None:
    with pytest.raises(ValidationError) as error:
        CommunicationAddress(channel=CommunicationChannel.EMAIL, value=value)

    assert error.value.code.startswith("communication.address")


def test_recipient_can_link_address_to_crm_reference() -> None:
    contact_id = ContactId(UUID("00000000-0000-0000-0000-000000000011"))
    recipient = CommunicationRecipient(
        address=CommunicationAddress(CommunicationChannel.EMAIL, "person@example.com"),
        display_name="  Person   Example ",
        reference=EntityReference("contact", contact_id),
    )

    assert recipient.display_name == "Person Example"
    assert recipient.reference == EntityReference("contact", contact_id)


def test_content_requires_at_least_one_body() -> None:
    with pytest.raises(ValidationError) as error:
        CommunicationContent(subject="Only a subject")

    assert error.value.code == "communication.content.body.required"


def test_content_preserves_multiline_body_and_normalizes_subject() -> None:
    content = CommunicationContent(
        subject="  Proposal   follow-up ",
        text_body="Hello\n\nNext step.",
    )

    assert content.subject == "Proposal follow-up"
    assert content.text_body == "Hello\n\nNext step."
