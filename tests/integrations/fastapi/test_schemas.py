"""Transport schema ↔ domain/facade qualification."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.activities import ActivityType
from pycrmkit.contacts import UNSET as CONTACT_UNSET
from pycrmkit.core.references import EntityReference
from pycrmkit.integrations.fastapi import (
    ActivityCreateRequest,
    ActivityParticipantSchema,
    ActivityResponse,
    AddressSchema,
    ContactCreateRequest,
    ContactEmailSchema,
    ContactResponse,
    ContactUpdateRequest,
    EntityReferenceSchema,
    LeadConversionRequest,
    LeadCreateRequest,
    LeadResponse,
    OpportunityCreateRequest,
    OpportunityMoveRequest,
    OpportunityResponse,
    OrganizationAddressSchema,
    OrganizationCreateRequest,
    OrganizationDomainSchema,
    OrganizationResponse,
    RelationshipCreateRequest,
    RelationshipEndpointSchema,
    RelationshipResponse,
    TaskCreateRequest,
    TaskPriorityName,
    TaskResponse,
    TimelineEntryResponse,
)
from pycrmkit.pipelines import Stage, StageTransition
from pycrmkit.relationships import RelationshipEntityKind


def test_contact_and_organization_schemas_drive_stable_facades() -> None:
    crm = CRM.memory()

    contact_request = ContactCreateRequest(
        first_name="Ada",
        last_name="Lovelace",
        emails=[
            ContactEmailSchema(
                value="Ada@Example.COM",
                is_primary=True,
            )
        ],
        addresses=[
            AddressSchema(
                line1="1 Analytical Way",
                city="London",
                country_code="gb",
            )
        ],
        metadata={"segment": "enterprise"},
    )
    contact = crm.contacts.create(**contact_request.to_domain_kwargs())

    organization_request = OrganizationCreateRequest(
        legal_name="Analytical Engines Ltd",
        domains=[
            OrganizationDomainSchema(
                value="Example.COM",
                is_primary=True,
            )
        ],
        addresses=[
            OrganizationAddressSchema(
                line1="2 Engine Street",
                city="London",
                country_code="GB",
            )
        ],
    )
    organization = crm.organizations.create(
        **organization_request.to_domain_kwargs()
    )

    contact_response = ContactResponse.from_domain(contact)
    organization_response = OrganizationResponse.from_domain(organization)

    assert contact_response.id == contact.id.value
    assert contact_response.emails[0].value == "Ada@Example.COM"
    assert contact.emails[0].normalized == "ada@example.com"
    assert contact_response.addresses[0].country_code == "GB"
    assert organization_response.id == organization.id.value
    assert organization.domains[0].normalized == "example.com"


def test_update_schema_preserves_omitted_vs_explicit_clear_semantics() -> None:
    patch = ContactUpdateRequest(display_name=None, metadata={})

    update = patch.to_domain()

    assert update.first_name is CONTACT_UNSET
    assert update.display_name is None
    assert update.metadata == {}


def test_relationship_schema_preserves_typed_endpoints() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(display_name="Ada")
    organization = crm.organizations.create(legal_name="Analytical Engines")

    request = RelationshipCreateRequest(
        source=RelationshipEndpointSchema(
            kind=RelationshipEntityKind.CONTACT,
            id=contact.id.value,
        ),
        target=RelationshipEndpointSchema(
            kind=RelationshipEntityKind.ORGANIZATION,
            id=organization.id.value,
        ),
        relationship_type="employment",
        role="founder",
        is_primary=True,
    )
    relationship = crm.relationships.create(**request.to_domain_kwargs())

    response = RelationshipResponse.from_domain(relationship)

    assert response.source.id == contact.id.value
    assert response.target.id == organization.id.value
    assert response.relationship_type == "employment"


def test_activity_task_and_timeline_transport_schemas_round_trip() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(display_name="Ada")
    reference = EntityReferenceSchema(
        kind="contact",
        id=contact.id.value,
    )

    activity_request = ActivityCreateRequest(
        type=ActivityType.MEETING,
        subject="Architecture review",
        participants=[
            ActivityParticipantSchema(
                reference=reference,
                role="customer",
                is_primary=True,
            )
        ],
    )
    activity = crm.activities.log(**activity_request.to_domain_kwargs())

    task_request = TaskCreateRequest(
        title="Prepare proposal",
        priority=TaskPriorityName.HIGH,
        references=[reference],
    )
    task = crm.tasks.create(**task_request.to_domain_kwargs())

    activity_response = ActivityResponse.from_domain(activity)
    task_response = TaskResponse.from_domain(task)
    timeline = crm.timeline.for_contact(contact.id)
    timeline_responses = [
        TimelineEntryResponse.from_domain(entry)
        for entry in timeline.items
    ]

    assert activity_response.participants[0].reference.id == contact.id.value
    assert task_response.priority is TaskPriorityName.HIGH
    assert {item.event_type for item in timeline_responses} == {
        "activity.created",
        "task.created",
    }


def test_sales_schemas_preserve_decimal_and_typed_ids() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(display_name="Ada")

    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("won", "Won", 10, terminal=True, outcome="won"),
        ),
        transitions=(StageTransition("new", "won"),),
    )

    lead_request = LeadCreateRequest(
        contact_id=contact.id.value,
        source="api",
    )
    lead = crm.leads.create(**lead_request.to_domain_kwargs())
    crm.leads.qualify(lead.id)

    conversion = LeadConversionRequest(
        name="API opportunity",
        estimated_value=Decimal("1250.50"),
        currency="EUR",
        pipeline_id="sales",
        idempotency_key="fastapi-a1-convert",
    )
    opportunity = crm.leads.convert(
        lead.id,
        **conversion.to_domain_kwargs(),
    )
    move = OpportunityMoveRequest(to="won")
    opportunity = crm.opportunities.move(opportunity.id, to=move.to)

    refreshed_lead = None
    with crm._runtime.uow_factory() as uow:
        refreshed_lead = uow.leads.get(lead.id)

    lead_response = LeadResponse.from_domain(refreshed_lead)
    opportunity_response = OpportunityResponse.from_domain(opportunity)

    assert lead_response.converted_opportunity_id == opportunity.id.value
    assert opportunity_response.estimated_value == Decimal("1250.50")
    assert opportunity_response.is_terminal is True


def test_opportunity_create_request_builds_domain_compatible_ids() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(display_name="Direct Opportunity")

    request = OpportunityCreateRequest(
        name="Direct deal",
        contact_id=contact.id.value,
        estimated_value=Decimal("42.00"),
        currency="EUR",
    )
    opportunity = crm.opportunities.create(**request.to_domain_kwargs())

    response = OpportunityResponse.from_domain(opportunity)

    assert response.contact_id == contact.id.value
    assert response.estimated_value == Decimal("42.00")


def test_entity_reference_schema_uses_generic_uuid_domain_reference() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(display_name="Reference")
    schema = EntityReferenceSchema(kind="contact", id=contact.id.value)

    reference = schema.to_domain()

    assert isinstance(reference, EntityReference)
    assert reference.kind == "contact"
    assert str(reference.id) == str(contact.id)


def test_response_schemas_are_json_serializable() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(
        display_name="Serialization",
        metadata={"created": datetime(2026, 9, 26, tzinfo=UTC).isoformat()},
    )

    payload = ContactResponse.from_domain(contact).model_dump(mode="json")

    assert payload["id"] == str(contact.id)
    assert payload["status"] == "active"
