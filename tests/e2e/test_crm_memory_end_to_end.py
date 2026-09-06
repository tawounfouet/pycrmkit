"""End-to-end qualification of the public 0.1 CRM facade."""

from __future__ import annotations

from datetime import UTC, datetime

from pycrmkit import CRM
from pycrmkit.contacts import ContactEmail
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.custom_fields import CustomFieldOption, CustomFieldType
from pycrmkit.events import DomainEvent
from pycrmkit.relationships import RelationshipEndpoint, RelationshipType

NOW = datetime(2026, 9, 6, 20, 10, tzinfo=UTC)


def test_contact_to_organization_relationship_tags_custom_fields_events_and_audit() -> None:
    crm = CRM.memory(clock=FixedClock(NOW)).with_context(
        actor_id="user-e2e",
        correlation_id="corr-e2e",
    )
    events: list[DomainEvent] = []
    for event_type in (
        "contact.created",
        "organization.created",
        "relationship.created",
        "tag.created",
        "tag.assigned",
        "custom_field.defined",
        "custom_field.value_set",
    ):
        crm.events.subscribe(event_type, events.append)

    contact = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(ContactEmail("ada@example.test", is_primary=True),),
    )
    organization = crm.organizations.create(legal_name="Analytical Engines Ltd")
    relationship = crm.relationships.create(
        source=RelationshipEndpoint.contact(contact.id),
        target=RelationshipEndpoint.organization(organization.id),
        relationship_type=RelationshipType("employment"),
        role="founder",
        is_primary=True,
    )

    contact_ref = EntityReference("contact", contact.id)
    vip = crm.tags.create("VIP")
    crm.tags.assign(vip.id, contact_ref)

    tier = crm.custom_fields.define(
        key="customer_tier",
        label="Customer Tier",
        field_type=CustomFieldType.ENUM,
        applies_to=("contact",),
        options=(
            CustomFieldOption("gold", "Gold"),
            CustomFieldOption("silver", "Silver"),
        ),
    )
    tier_value = crm.custom_fields.set_value(tier.id, contact_ref, "gold")

    assert crm.contacts.get(contact.id).display_name == "Ada Lovelace"
    assert crm.organizations.get(organization.id) == organization
    assert crm.relationships.get(relationship.id).relationship_type.code == "employment"
    assert crm.tags.list_for_entity(contact_ref).items == (vip,)
    assert crm.custom_fields.get_value(tier.id, contact_ref) == tier_value

    assert [str(event.type) for event in events] == [
        "contact.created",
        "organization.created",
        "relationship.created",
        "tag.created",
        "tag.assigned",
        "custom_field.defined",
        "custom_field.value_set",
    ]
    assert all(event.actor_id == "user-e2e" for event in events)
    assert all(event.correlation_id == "corr-e2e" for event in events)

    audit = crm.audit.by_correlation("corr-e2e")
    assert audit.total == 7
    assert {entry.action for entry in audit.items} == {
        "contact.created",
        "organization.created",
        "relationship.created",
        "tag.created",
        "tag.assigned",
        "custom_field.defined",
        "custom_field.value_set",
    }
