from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pycrmkit import CRM
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationRecipient,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderResult,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core import FixedClock
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, InvalidStateError, ValidationError

NOW = datetime(2026, 9, 30, 14, tzinfo=UTC)


class Provider:
    def send(self, message: EmailMessage) -> EmailProviderResult:
        return EmailProviderResult(
            provider="test",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="campaign-linkage-001",
        )


def crm_with_email() -> CRM:
    return CRM.memory(
        clock=FixedClock(NOW),
        email_provider=Provider(),
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sender@example.com",
        ),
        webhook_auto_delivery=False,
    )


def test_campaign_attribution_references_existing_crm_entity() -> None:
    crm = crm_with_email()
    contact = crm.contacts.create(display_name="Ada", source="LinkedIn")
    campaign = crm.campaigns.create(key="attribution", name="Attribution")
    target = EntityReference("contact", contact.id)

    reference = crm.campaigns.add_attribution(
        campaign.id,
        target,
        source="LinkedIn Organic",
        external_ref="utm-abc",
        metadata={"model": "reference-only"},
    )

    assert reference.source == "linkedin organic"
    assert crm.campaigns.attributions(campaign.id).items == (reference,)
    assert crm.campaigns.remove_attribution(
        campaign.id,
        target,
        source="LINKEDIN   ORGANIC",
        external_ref="utm-abc",
    )
    assert crm.campaigns.attributions(campaign.id).total == 0


def test_campaign_attribution_rejects_missing_target_and_duplicates() -> None:
    crm = crm_with_email()
    contact = crm.contacts.create(display_name="Ada")
    campaign = crm.campaigns.create(key="attribution-guards", name="Guards")
    target = EntityReference("contact", contact.id)

    crm.campaigns.add_attribution(campaign.id, target, source="event")

    with pytest.raises(DuplicateError) as duplicate:
        crm.campaigns.add_attribution(campaign.id, target, source="EVENT")
    assert duplicate.value.code == "campaign.attribution.duplicate"

    missing = EntityReference(
        "contact",
        ContactId.parse("00000000-0000-0000-0000-000000009998"),
    )
    with pytest.raises(ValidationError) as missing_error:
        crm.campaigns.add_attribution(campaign.id, missing, source="event")
    assert missing_error.value.code == "campaign.attribution.target.not_found"


def test_campaign_links_existing_communication_without_sending_new_one() -> None:
    crm = crm_with_email()
    contact = crm.contacts.create(display_name="Ada")
    contact_ref = EntityReference("contact", contact.id)
    record = crm.email.send(
        to=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "ada@example.com",
                ),
                reference=contact_ref,
            ),
        ),
        content=CommunicationContent(subject="Existing touchpoint", text_body="Hello"),
    )
    campaign = crm.campaigns.create(key="communication-link", name="Communication Link")

    link = crm.campaigns.link_communication(
        campaign.id,
        record.id,
        role="follow-up",
    )

    assert link.communication_id == record.id
    assert crm.campaigns.communication_links(campaign.id).items == (link,)
    assert crm.campaigns.communications(campaign.id).items == (record,)
    assert crm.email.for_contact(contact.id).total == 1

    assert crm.campaigns.unlink_communication(campaign.id, record.id)
    assert crm.campaigns.communications(campaign.id).total == 0
    assert crm.email.for_contact(contact.id).total == 1


def test_archived_campaign_rejects_linkage_mutations() -> None:
    crm = crm_with_email()
    contact = crm.contacts.create(display_name="Ada")
    target = EntityReference("contact", contact.id)
    campaign = crm.campaigns.create(key="archived-linkage", name="Archived")
    crm.campaigns.archive(campaign.id)

    with pytest.raises(InvalidStateError) as error:
        crm.campaigns.add_attribution(campaign.id, target, source="manual")
    assert error.value.code == "campaign.archived"
