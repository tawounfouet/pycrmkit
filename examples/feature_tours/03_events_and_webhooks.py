#!/usr/bin/env python3
"""PyCRMKit 1.2.0 - Feature Tour 03: Domain Events, Webhooks & Communications.

Demonstrates and verifies:
- In-process Domain Event Bus subscriptions & correlation tracking
- Outbound Webhooks registration, delivery simulation & secret rotation
- Communications (Email): recipient VO, rich content, EmailProvider protocol adapter
- Chronological communication history queries per contact
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pycrmkit import CRM, __version__
from pycrmkit.contacts import ContactEmail
from pycrmkit.communication.email.provider import EmailProviderResult, EmailDeliveryStatus
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationRecipient,
    CommunicationContent,
    CommunicationChannel,
)
from pycrmkit.core.references import EntityReference


class StandaloneMockEmailProvider:
    """Mock provider allowing 100% autonomous email transport tests."""

    def send(self, message):
        return EmailProviderResult(
            provider="standalone-mock-transport",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id=f"msg-tour-{str(message.intent_id)[:8]}",
        )


def run_tour() -> dict[str, object]:
    print("=" * 70)
    print("⚡ PYCRMKIT FEATURE TOUR 03: EVENTS, WEBHOOKS & COMMUNICATIONS")
    print(f"📦 PyCRMKit Version: {__version__}")
    print("=" * 70)

    # 1. CRM Initialization with Mock Email Provider
    crm = CRM.memory(email_provider=StandaloneMockEmailProvider()).with_context(
        actor_id="integration-engineer-07",
        correlation_id="events-tour-session",
    )
    print(f"\n[1/5] CRM initialisé avec EventBus & MockEmailProvider (Corrélation: {crm.context.correlation_id})")

    # 2. Event Subscription
    captured_events = []

    def on_contact_created(event):
        captured_events.append(event)
        print(f"      ⚡ Event intercepté : [{event.type}] pour agrégat {event.aggregate_id}")
        print(f"         Acteur: {event.actor_id} | Corrélation: {event.correlation_id}")

    crm.events.subscribe("contact.created", on_contact_created)

    contact = crm.contacts.create(
        first_name="Grace",
        last_name="Hopper",
        emails=(ContactEmail("grace.hopper@navy.mil", is_primary=True),),
    )
    print(f"[2/5] Contact créé : {contact.display_name} -> {len(captured_events)} événement(s) émis")

    # 3. Webhooks Management
    sub = crm.webhooks.register(
        url="https://api.external-monitoring.io/hooks/crm",
        events=("contact.created", "opportunity.created"),
        signing_secret="whsec_initial_secret_token_123",
    )
    print(f"[3/5] Webhook enregistré : ID {sub.id}")
    print(f"      URL cible : {sub.url}")
    print(f"      Secret de signature initial : {sub.signing_secret[:12]}...")

    # Delivery simulation
    deliveries = crm.webhooks.deliver(captured_events[0])
    print(f"      Livraison simulée pour l'événement : {len(deliveries)} tentative(s)")
    for d in deliveries:
        print(f"      • Subscription {d.subscription_id} -> État de livraison : {d.state}")

    # Secret rotation
    rotated_sub = crm.webhooks.rotate_secret(
        sub.id,
        signing_secret="whsec_rotated_production_key_456",
    )
    print(f"      Clé secrète renouvelée : {rotated_sub.signing_secret[:12]}...")

    # 4. Outbound Email Communication
    contact_ref = EntityReference("contact", contact.id)
    recipient_addr = CommunicationAddress(channel=CommunicationChannel.EMAIL, value="grace.hopper@navy.mil")
    sender_addr = CommunicationAddress(channel=CommunicationChannel.EMAIL, value="notifications@pycrmkit.io")

    recipients = (CommunicationRecipient(address=recipient_addr, display_name="Grace Hopper"),)
    content = CommunicationContent(
        subject="Bienvenue dans la suite PyCRMKit",
        text_body="Bonjour Grace, votre dossier a été initialisé avec succès.",
        html_body="<p>Bonjour <strong>Grace</strong>,<br>Votre dossier a été initialisé avec succès.</p>",
    )

    email_record = crm.email.send(
        to=recipients,
        sender=sender_addr,
        content=content,
        references=(contact_ref,),
        idempotency_key="welcome-grace-hopper-tour",
    )
    print(f"[4/5] Email expédié : ID {email_record.id}")
    print(f"      Objet : '{email_record.subject}' | Statut remise : {email_record.delivery_status}")

    # 5. History Query
    history = crm.email.for_contact(contact.id)
    print(f"[5/5] Historique de communication pour {contact.display_name} : {history.total} message(s)")
    for item in history.items:
        print(f"      • [{item.occurred_at.strftime('%H:%M:%S')}] {item.subject} (Statut: {item.delivery_status})")

    # Assertions
    assert len(captured_events) >= 1
    assert str(captured_events[0].type) == "contact.created"
    assert rotated_sub.signing_secret == "whsec_rotated_production_key_456"
    assert len(deliveries) >= 1
    assert history.total == 1
    assert history.items[0].subject == "Bienvenue dans la suite PyCRMKit"

    print("\n" + "=" * 70)
    print("✅ FEATURE TOUR 03 TERMINÉ AVEC SUCCÈS (Toutes les assertions vérifiées)")
    print("=" * 70 + "\n")

    return {
        "tour": "03_events_and_webhooks",
        "captured_events": len(captured_events),
        "webhook_id": str(sub.id),
        "email_record_id": str(email_record.id),
        "status": "PASS",
    }


if __name__ == "__main__":
    run_tour()
