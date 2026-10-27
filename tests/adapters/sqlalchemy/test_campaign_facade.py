"""SQLAlchemy Campaign facade capability qualification."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.events import InProcessEventBus
from pycrmkit.segments import Predicate, QueryOperator
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

NOW = datetime(2026, 9, 30, 18, tzinfo=UTC)


class Provider:
    def send(self, message: EmailMessage) -> EmailProviderResult:
        del message
        return EmailProviderResult(
            provider="test",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="sqlalchemy-campaign-001",
        )


def test_sqlalchemy_crm_exposes_complete_campaign_facade(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'campaign-facade.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    bus = InProcessEventBus()

    def uow_factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(factory, event_publisher=bus)

    crm = CRM(
        uow_factory=uow_factory,
        event_bus=bus,
        clock=FixedClock(NOW),
        email_provider=Provider(),
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sender@example.com",
        ),
        webhook_auto_delivery=False,
    )

    contact = crm.contacts.create(display_name="Ada", source="LinkedIn")
    contact_ref = EntityReference("contact", contact.id)
    campaign = crm.campaigns.create(key="sql-campaign", name="SQL Campaign")

    member = crm.campaigns.add_member(campaign.id, contact_ref)
    segment = crm.segments.create_dynamic(
        key="sql-linkedin",
        name="SQL LinkedIn",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "linkedin"),
    )
    source = crm.campaigns.attach_segment_source(campaign.id, segment.id)
    attribution = crm.campaigns.add_attribution(
        campaign.id,
        contact_ref,
        source="organic",
    )
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
        content=CommunicationContent(subject="Touchpoint", text_body="Hello"),
    )
    link = crm.campaigns.link_communication(
        campaign.id,
        record.id,
        role="follow-up",
    )

    assert member.entity == contact_ref
    assert source.member_count == 1
    assert crm.campaigns.audience_count(campaign.id) == 1
    assert crm.campaigns.attributions(campaign.id).items == (attribution,)
    assert crm.campaigns.communication_links(campaign.id).items == (link,)
    assert crm.campaigns.communications(campaign.id).items == (record,)

    engine.dispose()
