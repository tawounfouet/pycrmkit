"""Privacy regression tests for domain events and audit evidence."""

from __future__ import annotations

from pycrmkit import CRM
from pycrmkit.contacts import Address, ContactEmail, ContactPhone
from pycrmkit.events import DomainEvent, EventSerializer, default_event_registry


def test_contact_event_and_audit_do_not_copy_customer_payload_values() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    emitted: list[DomainEvent] = []
    crm.events.subscribe("contact.created", emitted.append)

    email = "ada.private@example.com"
    phone = "+33612345678"
    street = "42 Confidential Street"
    contact = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(ContactEmail(email, is_primary=True),),
        phones=(ContactPhone(phone, is_primary=True),),
        addresses=(Address(street, "Paris", postal_code="75001"),),
        metadata={"private_note": "never-copy-this"},
    )

    assert len(emitted) == 1
    encoded = EventSerializer(default_event_registry()).dumps(emitted[0])
    for sensitive in (email, phone, street, "never-copy-this"):
        assert sensitive not in encoded

    audit = crm.audit.for_entity("contact", contact.id)
    assert audit.total == 1
    audit_text = repr(audit.items[0].changes)
    for sensitive in (email, phone, street, "never-copy-this"):
        assert sensitive not in audit_text


def test_external_identity_events_expose_system_but_not_external_identifier() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    events: list[DomainEvent] = []
    crm.events.subscribe("external_identity.attached", events.append)
    crm.events.subscribe("external_identity.detached", events.append)

    contact = crm.contacts.create(display_name="External Identity Privacy")
    external_id = "customer-secret-000042"

    crm.external_identities.attach(
        contact,
        system="legacy_crm",
        external_id=external_id,
    )
    crm.external_identities.detach("legacy_crm", external_id)

    assert [str(event.type) for event in events] == [
        "external_identity.attached",
        "external_identity.detached",
    ]
    for event in events:
        assert dict(event.payload) == {"system": "legacy_crm"}
        assert external_id not in repr(event.payload)
