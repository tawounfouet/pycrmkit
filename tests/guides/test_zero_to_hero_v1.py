"""Executable examples for the V1 Zero-to-Hero guides."""

from datetime import UTC, datetime

import pytest

from pycrmkit import CRM, __version__
from pycrmkit.activities import ActivityParticipant
from pycrmkit.contacts import (
    Address,
    ContactEmail,
    ContactPhone,
    ContactQuery,
    ContactStatus,
    ContactUpdate,
)
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import (
    CustomFieldDefinitionQuery,
    CustomFieldDefinitionRevision,
    CustomFieldOption,
    CustomFieldType,
)
from pycrmkit.exceptions import (
    ConflictError,
    DuplicateError,
    InvalidStateError,
    ValidationError,
)
from pycrmkit.organizations import (
    OrganizationAddress,
    OrganizationDomain,
    OrganizationQuery,
    OrganizationStatus,
    OrganizationUpdate,
)
from pycrmkit.relationships import (
    RelationshipEndpoint,
    RelationshipEntityKind,
    RelationshipQuery,
    RelationshipType,
    RelationshipUpdate,
)
from pycrmkit.tags import TagName, TagQuery


def test_zero_to_hero_getting_started_example() -> None:
    assert __version__.startswith("1.0.")

    crm = CRM.memory().with_context(
        actor_id="guide-user",
        correlation_id="zero-to-hero-001",
    )
    contact = crm.contacts.create(
        first_name="Grace",
        last_name="Hopper",
    )

    assert crm.contacts.get(contact.id) == contact
    assert contact.display_name == "Grace Hopper"


def test_zero_to_hero_first_crm_example() -> None:
    crm = CRM.memory().with_context(
        actor_id="guide-user",
        correlation_id="first-crm-001",
    )

    contact = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(
            ContactEmail(
                "ada@example.com",
                is_primary=True,
            ),
        ),
    )
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
        source="zero-to-hero",
    )
    relationship = crm.relationships.create(
        source=RelationshipEndpoint.contact(contact.id),
        target=RelationshipEndpoint.organization(organization.id),
        relationship_type=RelationshipType("employment"),
        role="founder",
        is_primary=True,
    )

    contact_ref = EntityReference(kind="contact", id=contact.id)
    organization_ref = EntityReference(kind="organization", id=organization.id)

    activity = crm.activities.log(
        type="meeting",
        subject="CRM discovery session",
        participants=(
            ActivityParticipant(
                reference=contact_ref,
                role="customer",
                is_primary=True,
            ),
        ),
        references=(organization_ref,),
    )

    task = crm.tasks.create(
        title="Prepare the first proposal",
        priority="high",
        references=(contact_ref, organization_ref),
    )
    crm.tasks.start(task.id)
    completed_task = crm.tasks.complete(task.id)

    timeline = crm.timeline.for_contact(contact.id)
    event_types = {str(entry.event_type) for entry in timeline.items}

    assert crm.contacts.get(contact.id) == contact
    assert crm.organizations.get(organization.id) == organization
    assert crm.relationships.get(relationship.id) == relationship
    assert crm.activities.get(activity.id) == activity
    assert crm.tasks.get(task.id) == completed_task
    assert completed_task.status.value == "completed"
    assert {
        "activity.created",
        "task.created",
        "task.started",
        "task.completed",
    } <= event_types



def test_zero_to_hero_contacts_mastery_example() -> None:
    crm = CRM.memory().with_context(
        actor_id="guide-user",
        correlation_id="contacts-guide-001",
    )

    contact = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(
            ContactEmail(
                "Ada@Example.com",
                is_primary=True,
            ),
        ),
        phones=(
            ContactPhone(
                "+44 20 7946 0958",
                is_primary=True,
            ),
        ),
        addresses=(
            Address(
                line1="12 St James's Square",
                city="London",
                postal_code="SW1Y 4LB",
                country_code="gb",
                is_primary=True,
            ),
        ),
        source="zero-to-hero",
        metadata={"segment": "strategic"},
    )

    assert contact.display_name == "Ada Lovelace"
    assert contact.emails[0].normalized == "ada@example.com"
    assert contact.phones[0].normalized == "+442079460958"
    assert contact.addresses[0].country_code == "GB"

    updated = crm.contacts.update(
        contact.id,
        ContactUpdate(
            last_name="Byron",
            source=None,
        ),
    )
    assert updated.display_name == "Ada Byron"
    assert updated.source is None

    email_page = crm.contacts.search(
        ContactQuery(email="ADA@EXAMPLE.COM"),
        OffsetPageRequest(limit=10),
    )
    assert email_page.items == (updated,)
    assert email_page.total == 1
    assert email_page.has_next is False
    assert email_page.has_previous is False

    name_page = crm.contacts.search(ContactQuery(name="byr"))
    assert name_page.items == (updated,)

    archived = crm.contacts.archive(contact.id)
    assert archived.status is ContactStatus.ARCHIVED
    assert crm.contacts.search().total == 0

    archived_page = crm.contacts.search(
        ContactQuery(
            status=ContactStatus.ARCHIVED,
            include_archived=True,
        )
    )
    assert archived_page.items == (archived,)

    with pytest.raises(InvalidStateError, match="archived contacts cannot be updated"):
        crm.contacts.update(
            contact.id,
            ContactUpdate(last_name="Changed"),
        )


def test_zero_to_hero_contacts_invariant_examples() -> None:
    crm = CRM.memory()

    with pytest.raises(ValidationError) as missing_identity:
        crm.contacts.create()
    assert missing_identity.value.code == "contact.identity.required"

    with pytest.raises(ValidationError) as multiple_primary:
        crm.contacts.create(
            display_name="Ada Lovelace",
            emails=(
                ContactEmail("ada@example.com", is_primary=True),
                ContactEmail("ada@example.org", is_primary=True),
            ),
        )
    assert multiple_primary.value.code == "contact.email.multiple_primary"

    with pytest.raises(ConflictError) as duplicate_email:
        crm.contacts.create(
            display_name="Ada Lovelace",
            emails=(
                ContactEmail("Ada@Example.com"),
                ContactEmail("ada@example.com"),
            ),
        )
    assert duplicate_email.value.code == "contact.email.duplicate"

    inactive = crm.contacts.create(
        display_name="Dormant Customer",
        status=ContactStatus.INACTIVE,
    )
    assert inactive.status is ContactStatus.INACTIVE

    with pytest.raises(InvalidStateError) as direct_archive:
        crm.contacts.update(
            inactive.id,
            ContactUpdate(status=ContactStatus.ARCHIVED),
        )
    assert direct_archive.value.code == "contact.update.archive_requires_archive_operation"



def test_zero_to_hero_organizations_mastery_example() -> None:
    crm = CRM.memory().with_context(
        actor_id="guide-user",
        correlation_id="organizations-guide-001",
    )

    organization = crm.organizations.create(
        legal_name="Example Holdings SAS",
        trading_name="Example CRM",
        registration_number="123 456 789",
        tax_id="FR00123456789",
        domains=(
            OrganizationDomain(
                "Example.COM.",
                is_primary=True,
            ),
        ),
        addresses=(
            OrganizationAddress(
                line1="10 avenue des Entreprises",
                city="Paris",
                postal_code="75008",
                country_code="fr",
                is_primary=True,
            ),
        ),
        source="zero-to-hero",
        metadata={"segment": "enterprise"},
    )

    assert organization.display_name == "Example CRM"
    assert organization.domains[0].normalized == "example.com"
    assert organization.addresses[0].country_code == "FR"

    updated = crm.organizations.update(
        organization.id,
        OrganizationUpdate(
            trading_name="Example Cloud",
            source=None,
        ),
    )
    assert updated.display_name == "Example Cloud"
    assert updated.source is None

    domain_page = crm.organizations.search(
        OrganizationQuery(domain="EXAMPLE.COM."),
        OffsetPageRequest(limit=10),
    )
    assert domain_page.items == (updated,)
    assert domain_page.total == 1

    name_page = crm.organizations.search(OrganizationQuery(name="cloud"))
    assert name_page.items == (updated,)

    registration_page = crm.organizations.search(
        OrganizationQuery(registration_number="123 456 789")
    )
    assert registration_page.items == (updated,)

    archived = crm.organizations.archive(organization.id)
    assert archived.status is OrganizationStatus.ARCHIVED
    assert crm.organizations.search().total == 0

    archived_page = crm.organizations.search(
        OrganizationQuery(
            status=OrganizationStatus.ARCHIVED,
            include_archived=True,
        )
    )
    assert archived_page.items == (archived,)

    with pytest.raises(
        InvalidStateError,
        match="archived organizations cannot be updated",
    ):
        crm.organizations.update(
            organization.id,
            OrganizationUpdate(trading_name="Changed"),
        )


def test_zero_to_hero_organizations_invariant_examples() -> None:
    crm = CRM.memory()

    with pytest.raises(ValidationError) as blank_legal_name:
        crm.organizations.create(legal_name="   ")
    assert blank_legal_name.value.code == "organization.legal_name.required"

    with pytest.raises(ValidationError) as invalid_domain:
        OrganizationDomain("https://example.com")
    assert invalid_domain.value.code == "organization.domain.invalid"

    with pytest.raises(ValidationError) as multiple_primary:
        crm.organizations.create(
            legal_name="Example Holdings SAS",
            domains=(
                OrganizationDomain("example.com", is_primary=True),
                OrganizationDomain("example.org", is_primary=True),
            ),
        )
    assert multiple_primary.value.code == "organization.domain.multiple_primary"

    with pytest.raises(ConflictError) as duplicate_domain:
        crm.organizations.create(
            legal_name="Example Holdings SAS",
            domains=(
                OrganizationDomain("Example.COM"),
                OrganizationDomain("example.com."),
            ),
        )
    assert duplicate_domain.value.code == "organization.domain.duplicate"

    inactive = crm.organizations.create(
        legal_name="Dormant Holdings Ltd",
        status=OrganizationStatus.INACTIVE,
    )
    assert inactive.status is OrganizationStatus.INACTIVE

    with pytest.raises(InvalidStateError) as direct_archive:
        crm.organizations.update(
            inactive.id,
            OrganizationUpdate(status=OrganizationStatus.ARCHIVED),
        )
    assert direct_archive.value.code == (
        "organization.update.archive_requires_archive_operation"
    )



def test_zero_to_hero_relationships_mastery_example() -> None:
    crm = CRM.memory().with_context(
        actor_id="guide-user",
        correlation_id="relationships-guide-001",
    )

    contact = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
    )
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )

    source = RelationshipEndpoint.contact(contact.id)
    target = RelationshipEndpoint.organization(organization.id)

    relationship = crm.relationships.create(
        source=source,
        target=target,
        relationship_type=RelationshipType("Board Member"),
        role="founder",
        title="Director",
        is_primary=True,
        metadata={"source_system": "manual"},
    )

    assert relationship.source == source
    assert relationship.target == target
    assert relationship.source.kind is RelationshipEntityKind.CONTACT
    assert relationship.target.kind is RelationshipEntityKind.ORGANIZATION
    assert str(relationship.relationship_type) == "board-member"
    assert relationship.is_ended is False

    updated = crm.relationships.update(
        relationship.id,
        RelationshipUpdate(
            title="Executive Director",
            is_primary=False,
        ),
    )
    assert updated.title == "Executive Director"
    assert updated.is_primary is False

    by_entity = crm.relationships.search(
        RelationshipQuery(entity=source),
        OffsetPageRequest(limit=10),
    )
    assert by_entity.items == (updated,)
    assert by_entity.total == 1

    by_direction = crm.relationships.search(
        RelationshipQuery(
            source=source,
            target=target,
            relationship_type=RelationshipType("board_member"),
        )
    )
    assert by_direction.items == (updated,)

    ended = crm.relationships.end(relationship.id)
    assert ended.is_ended is True
    assert crm.relationships.search().total == 0

    history = crm.relationships.search(
        RelationshipQuery(include_ended=True)
    )
    assert history.items == (ended,)

    with pytest.raises(
        InvalidStateError,
        match="ended relationships cannot be updated",
    ):
        crm.relationships.update(
            relationship.id,
            RelationshipUpdate(title="Changed"),
        )


def test_zero_to_hero_relationships_invariant_examples() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(display_name="Ada Lovelace")
    other_contact = crm.contacts.create(display_name="Charles Babbage")
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )

    contact_endpoint = RelationshipEndpoint.contact(contact.id)

    with pytest.raises(ConflictError) as self_link:
        crm.relationships.create(
            source=contact_endpoint,
            target=contact_endpoint,
            relationship_type=RelationshipType("peer"),
        )
    assert self_link.value.code == "relationship.self_link"

    normalized = RelationshipType("  Board_Member  ")
    assert normalized.code == "board-member"

    with pytest.raises(ValidationError) as missing_type:
        RelationshipType("   ")
    assert missing_type.value.code == "relationship.type.required"

    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 1, tzinfo=UTC)

    historical = crm.relationships.create(
        source=RelationshipEndpoint.contact(other_contact.id),
        target=RelationshipEndpoint.organization(organization.id),
        relationship_type=RelationshipType("employment"),
        valid_from=start,
        valid_until=end,
    )

    assert historical.is_active(datetime(2025, 6, 1, tzinfo=UTC))
    assert not historical.is_active(datetime(2026, 1, 1, tzinfo=UTC))

    active_page = crm.relationships.search(
        RelationshipQuery(
            active_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
    )
    assert historical in active_page.items

    inactive_page = crm.relationships.search(
        RelationshipQuery(
            active_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert historical not in inactive_page.items

    with pytest.raises(ValidationError) as invalid_interval:
        crm.relationships.create(
            source=RelationshipEndpoint.contact(contact.id),
            target=RelationshipEndpoint.organization(organization.id),
            relationship_type=RelationshipType("employment"),
            valid_from=end,
            valid_until=start,
        )
    assert invalid_interval.value.code == "relationship.validity.invalid_interval"



def test_zero_to_hero_tags_mastery_example() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    contact_ref = EntityReference(
        kind="contact",
        id=contact.id,
    )

    vip = crm.tags.create(
        "  VIP   Client ",
        metadata={"segment": "strategic"},
    )
    assert vip.name.value == "VIP Client"
    assert vip.name.normalized == "vip client"

    assignment = crm.tags.assign(
        vip.id,
        contact_ref,
    )
    assert assignment.tag_id == vip.id
    assert assignment.entity == contact_ref

    assigned = crm.tags.list_for_entity(
        contact_ref,
        OffsetPageRequest(limit=10),
    )
    assert assigned.items == (vip,)
    assert assigned.total == 1

    found = crm.tags.search(
        TagQuery(
            name=TagName(" vip client "),
        )
    )
    assert found.items == (vip,)

    with pytest.raises(DuplicateError) as duplicate_assignment:
        crm.tags.assign(
            vip.id,
            contact_ref,
        )
    assert duplicate_assignment.value.code == "tag.assignment.duplicate"

    assert crm.tags.remove(vip.id, contact_ref) is True
    assert crm.tags.remove(vip.id, contact_ref) is False
    assert crm.tags.list_for_entity(contact_ref).items == ()


def test_zero_to_hero_tags_invariant_examples() -> None:
    crm = CRM.memory()

    with pytest.raises(ValidationError) as blank_name:
        crm.tags.create("   ")
    assert blank_name.value.code == "tag.name.required"

    crm.tags.create("Priority")
    with pytest.raises(DuplicateError) as duplicate_name:
        crm.tags.create(" priority ")
    assert duplicate_name.value.code == "tag.duplicate"


def test_zero_to_hero_custom_fields_mastery_example() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )
    contact_ref = EntityReference(
        kind="contact",
        id=contact.id,
    )
    organization_ref = EntityReference(
        kind="organization",
        id=organization.id,
    )

    tier = crm.custom_fields.define(
        key="Customer Tier",
        label="Customer Tier",
        field_type=CustomFieldType.ENUM,
        applies_to=("contact", "organization"),
        options=(
            CustomFieldOption("gold", "Gold"),
            CustomFieldOption("silver", "Silver"),
        ),
    )

    assert tier.key == "customer_tier"
    assert tier.schema_version == 1

    first_value = crm.custom_fields.set_value(
        tier.id,
        contact_ref,
        "GOLD",
    )
    assert first_value.value == "gold"
    assert first_value.schema_version == 1

    tier_v2 = crm.custom_fields.revise(
        tier.id,
        CustomFieldDefinitionRevision(
            label="CRM Customer Tier",
            options=(
                CustomFieldOption("gold", "Gold"),
                CustomFieldOption("silver", "Silver"),
                CustomFieldOption("bronze", "Bronze"),
            ),
        ),
    )

    assert tier_v2.id == tier.id
    assert tier_v2.schema_version == 2
    assert crm.custom_fields.get_definition(tier.id, version=1).schema_version == 1
    assert crm.custom_fields.get_definition(tier.id).schema_version == 2

    second_value = crm.custom_fields.set_value(
        tier.id,
        contact_ref,
        "bronze",
    )
    assert second_value.id == first_value.id
    assert second_value.value == "bronze"
    assert second_value.schema_version == 2

    definitions = crm.custom_fields.search_definitions(
        CustomFieldDefinitionQuery(
            key="customer-tier",
        ),
        OffsetPageRequest(limit=10),
    )
    assert definitions.items == (tier_v2,)

    assert crm.custom_fields.list_values(
        contact_ref,
    ).items == (second_value,)

    manager = crm.custom_fields.define(
        key="account_manager",
        label="Account Manager",
        field_type=CustomFieldType.REFERENCE,
        applies_to=("organization",),
        reference_kinds=("contact",),
    )
    manager_value = crm.custom_fields.set_value(
        manager.id,
        organization_ref,
        contact_ref,
    )
    assert manager_value.value == contact_ref


def test_zero_to_hero_custom_fields_invariant_examples() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )
    contact_ref = EntityReference(
        kind="contact",
        id=contact.id,
    )
    organization_ref = EntityReference(
        kind="organization",
        id=organization.id,
    )

    contact_only = crm.custom_fields.define(
        key="preferred_name",
        label="Preferred Name",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )

    with pytest.raises(ValidationError) as wrong_entity:
        crm.custom_fields.set_value(
            contact_only.id,
            organization_ref,
            "Example",
        )
    assert wrong_entity.value.code == "custom_field.entity_kind.not_allowed"

    required_score = crm.custom_fields.define(
        key="account_score",
        label="Account Score",
        field_type=CustomFieldType.INTEGER,
        applies_to=("contact",),
        required=True,
    )
    with pytest.raises(ValidationError) as required_value:
        crm.custom_fields.set_value(
            required_score.id,
            contact_ref,
            None,
        )
    assert required_value.value.code == "custom_field.value.required"

    inactive = crm.custom_fields.revise(
        contact_only.id,
        CustomFieldDefinitionRevision(
            active=False,
        ),
    )
    assert inactive.active is False

    with pytest.raises(InvalidStateError) as inactive_definition:
        crm.custom_fields.set_value(
            inactive.id,
            contact_ref,
            "Ada",
        )
    assert inactive_definition.value.code == "custom_field.inactive"

    with pytest.raises(ValidationError) as enum_without_options:
        crm.custom_fields.define(
            key="risk_level",
            label="Risk Level",
            field_type=CustomFieldType.ENUM,
            applies_to=("contact",),
        )
    assert enum_without_options.value.code == "custom_field.option.required"
