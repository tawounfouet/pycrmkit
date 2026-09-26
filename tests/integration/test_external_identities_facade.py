"""CRM facade integration for external identities."""

from __future__ import annotations

from pycrmkit import CRM
from pycrmkit.events import DomainEvent


def test_crm_external_identities_accepts_domain_entities_and_is_idempotent() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    events: list[DomainEvent] = []
    crm.events.subscribe("external_identity.attached", events.append)

    identity = crm.external_identities.attach(
        contact,
        system="hubspot",
        external_id="123456",
        metadata={"portal": "eu"},
    )
    replay = crm.external_identities.attach(
        contact,
        system="HUBSPOT",
        external_id="123456",
    )

    assert replay == identity
    assert len(events) == 1
    assert crm.external_identities.resolve("hubspot", "123456") == identity
    assert crm.external_identities.list_for_entity(contact).items == (identity,)


def test_crm_external_identity_detach_emits_once_and_is_idempotent() -> None:
    crm = CRM.memory()
    organization = crm.organizations.create(legal_name="Analytical Engines Ltd")
    events: list[DomainEvent] = []
    crm.events.subscribe("external_identity.detached", events.append)

    crm.external_identities.attach(
        organization,
        system="legacy_crm",
        external_id="ORG-7",
    )

    assert crm.external_identities.detach("legacy_crm", "ORG-7") is True
    assert crm.external_identities.detach("legacy_crm", "ORG-7") is False
    assert len(events) == 1
    assert events[0].aggregate_type == "organization"
