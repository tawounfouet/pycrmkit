"""Feature Tour 06: Campaigns v1.2.0, Attribution, Linkage & DataOps.

This autonomous script demonstrates and tests the core campaign capabilities
introduced in PyCRMKit 1.2.0:
- Campaign lifecycle (create, update, activate, complete)
- Optimistic concurrency control (expected_revision & ConflictError on stale updates)
- Direct member management (unit and batch additions)
- Dynamic segment source attachment & audience resolution
- Communication linkage & touchpoint attribution without leaking body content
- Bounded DataOps import check & paginated JSONL audience export
"""

from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure src/ is importable
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pycrmkit import CRM, __version__
from pycrmkit.campaigns import CampaignUpdate
from pycrmkit.campaigns.data_operations import (
    MAX_CAMPAIGN_IMPORT_ROWS,
    export_campaign_records,
)
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationRecipient,
)
from pycrmkit.communication.email.provider import (
    EmailDeliveryStatus,
    EmailProviderResult,
)
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ConflictError
from pycrmkit.segments import Predicate, QueryOperator


class StandaloneMockEmailProvider:
    """In-memory mock email provider for isolated campaign communication testing."""

    def send(self, message) -> EmailProviderResult:
        return EmailProviderResult(
            provider="mock-campaign-mailer",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id=f"msg-tour-{str(message.intent_id)[:8]}",
        )


def run_tour() -> dict[str, object]:
    """Execute the full campaigns tour and assert system invariants."""
    print("=" * 70)
    print("🎯 PYCRMKIT FEATURE TOUR 06: CAMPAIGNS V1.2.0 & LINKAGE")
    print(f"📦 PyCRMKit Version: {__version__}")
    print("=" * 70)

    # 1. CRM Setup with Mock Email Provider
    crm = CRM.memory(email_provider=StandaloneMockEmailProvider()).with_context(
        actor_id="marketing-lead-12",
        correlation_id="tour-campaigns-session",
    )
    print("\n[1/7] CRM initialisé avec MockEmailProvider et contexte d'acteur.")

    # 2. Campaign Creation & Optimistic Concurrency Control
    now = datetime.now(timezone.utc)
    campaign = crm.campaigns.create(
        key="summit-europe-2026",
        name="Campagne Tech Summit Europe 2026",
        description="Campagne multi-canal de lancement du sommet tech européen",
        starts_at=now,
        ends_at=now + timedelta(days=45),
        metadata={
            "budget_allocated": 75000,
            "target_accounts": 150,
            "channels": ["email", "linkedin", "webinar"],
        },
    )
    assert campaign.revision == 1
    assert campaign.status.value == "draft"
    print(f"[2/7] Campagne créée : '{campaign.name}' [Clé: {campaign.key}]")
    print(f"      Statut initial : {campaign.status.value} | Révision initiale : {campaign.revision}")

    # Valid update with expected_revision=1 -> revision becomes 2
    updated_campaign = crm.campaigns.update(
        campaign.id,
        CampaignUpdate(name="Tech Summit Europe 2026 — Official Launch"),
        expected_revision=1,
    )
    assert updated_campaign.revision == 2
    print(f"      Mise à jour réussie : '{updated_campaign.name}' (Nouvelle révision: {updated_campaign.revision})")

    # Stale update with expected_revision=1 must raise ConflictError
    conflict_caught = False
    try:
        crm.campaigns.update(
            campaign.id,
            CampaignUpdate(name="Tentative de mise à jour concurrente"),
            expected_revision=1,  # Stale: revision is now 2
        )
    except ConflictError:
        conflict_caught = True
    assert conflict_caught, "ConflictError attendu lors d'une révision concurrente obsolète"
    print("      Protection de concurrence optimiste vérifiée (ConflictError levé sur révision 1 obsolète).")

    # 3. Direct Members Management
    vip_contact = crm.contacts.create(
        first_name="Victor",
        last_name="Hugo",
        source="direct_invite",
    )
    web_contact1 = crm.contacts.create(
        first_name="George",
        last_name="Sand",
        source="web_event",
    )
    web_contact2 = crm.contacts.create(
        first_name="Gustave",
        last_name="Flaubert",
        source="web_event",
    )

    direct_member = crm.campaigns.add_member(
        campaign.id,
        EntityReference("contact", vip_contact.id),
        source="vip_guest_list",
        metadata={"tier": "vip_gold", "seat_preference": "front_row"},
    )
    assert direct_member.source == "vip_guest_list"
    print(f"\n[3/7] Membre direct ajouté : {vip_contact.display_name} (Source: {direct_member.source})")

    # 4. Segment Source Attachment & Audience Resolution
    web_segment = crm.segments.create_dynamic(
        key="web-attendees",
        name="Participants Web Event",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "web_event"),
    )
    attached_source = crm.campaigns.attach_segment_source(campaign.id, web_segment.id)
    assert attached_source.member_count == 2
    print(f"[4/7] Segment source rattaché : '{web_segment.name}' ({attached_source.member_count} membres capturés)")

    # Audience resolution (1 direct VIP + 2 from segment = 3 total)
    total_audience = crm.campaigns.audience_count(campaign.id)
    audience_page = crm.campaigns.audience(campaign.id)
    assert total_audience == 3
    assert len(audience_page.items) == 3
    vip_in_audience = crm.campaigns.contains(campaign.id, EntityReference("contact", vip_contact.id))
    assert vip_in_audience is True
    print(f"      Audience dédupliquée totale résolue : {total_audience} contacts")
    for ref in audience_page.items:
        print(f"      • [{ref.kind}] {ref.id}")

    # 5. Communication Touchpoint Linkage & Attribution
    recipient = CommunicationRecipient(
        address=CommunicationAddress(channel=CommunicationChannel.EMAIL, value="victor.hugo@academie.fr"),
        display_name=vip_contact.display_name,
    )
    sender = CommunicationAddress(channel=CommunicationChannel.EMAIL, value="summit@pycrmkit.io")
    content = CommunicationContent(
        subject="Invitation exclusive : Tech Summit Europe 2026",
        text_body="Cher Victor, nous avons le plaisir de vous inviter...",
    )
    comm_record = crm.email.send(
        to=(recipient,),
        sender=sender,
        content=content,
        references=(EntityReference("contact", vip_contact.id),),
    )

    # Link communication to campaign without leaking body content
    comm_link = crm.campaigns.link_communication(
        campaign.id,
        communication_id=comm_record.id,
        role="invitation_email",
        metadata={"channel": "email", "batch": "wave_1"},
    )
    assert comm_link.role == "invitation_email"
    print(f"\n[5/7] Communication liée : Comm ID {comm_link.communication_id} [Rôle: {comm_link.role}]")

    # Add attribution
    attribution = crm.campaigns.add_attribution(
        campaign.id,
        target=EntityReference("contact", vip_contact.id),
        source="vip_rsvp",
        external_ref="rsvp-ticket-001",
        metadata={"rsvp_status": "confirmed"},
    )
    assert attribution.source == "vip_rsvp"
    print(f"      Attribution enregistrée : [{attribution.target.kind}] {attribution.target.id} (Source: {attribution.source})")

    # 6. DataOps Export & Bounded Import Limit Check
    assert MAX_CAMPAIGN_IMPORT_ROWS == 1000
    export_buffer = io.StringIO()
    exported_count = export_campaign_records(
        crm.campaigns,
        campaign.id,
        export_buffer,
        kind="audience",
        format="jsonl",
    )
    assert exported_count == 3
    exported_data = export_buffer.getvalue().strip()
    print(f"\n[6/7] DataOps Campagnes validé :")
    print(f"      • Limite maximale d'import par lot : {MAX_CAMPAIGN_IMPORT_ROWS} lignes")
    print(f"      • Export JSONL audience : {exported_count} lignes exportées")
    for sample_line in exported_data.splitlines()[:2]:
        print(f"        {sample_line}")

    # 7. Campaign Lifecycle Transitions (Activate & Complete)
    activated = crm.campaigns.activate(campaign.id)
    assert activated.status.value == "active"
    print(f"\n[7/7] Cycle de vie de la campagne :")
    print(f"      • Statut après activation : {activated.status.value}")

    completed = crm.campaigns.complete(campaign.id)
    assert completed.status.value == "completed"
    print(f"      • Statut après clôture   : {completed.status.value}")

    print("\n" + "=" * 70)
    print("✅ FEATURE TOUR 06 TERMINÉ AVEC SUCCÈS (Toutes les assertions vérifiées)")
    print("=" * 70)

    return {
        "campaign_id": str(campaign.id),
        "campaign_key": campaign.key,
        "revision": completed.revision,
        "audience_count": total_audience,
        "status": completed.status.value,
        "attribution_source": attribution.source,
    }


if __name__ == "__main__":
    run_tour()
