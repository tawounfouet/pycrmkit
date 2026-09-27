"""Executable examples for the V1 Zero-to-Hero guides."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from pycrmkit import CRM, __version__
from pycrmkit.activities import (
    ActivityDirection,
    ActivityParticipant,
    ActivityQuery,
    ActivityService,
    ActivityType,
    ActivityUpdate,
)
from pycrmkit.contacts import (
    Address,
    ContactEmail,
    ContactId,
    ContactPhone,
    ContactQuery,
    ContactStatus,
    ContactUpdate,
)
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.custom_fields import (
    CustomFieldDefinitionQuery,
    CustomFieldDefinitionRevision,
    CustomFieldOption,
    CustomFieldType,
)
from pycrmkit.events import DomainEvent
from pycrmkit.exceptions import (
    ConflictError,
    DuplicateError,
    InvalidStateError,
    ValidationError,
)
from pycrmkit.leads import LeadQuery, LeadService, LeadStatus
from pycrmkit.opportunities import (
    OpportunityQuery,
    OpportunityService,
    OpportunityStatus,
)
from pycrmkit.pipelines import (
    InvalidStageTransition,
    Pipeline,
    PipelineTransitionPolicy,
    Stage,
    StageOutcome,
    StageTransition,
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
from pycrmkit.storage.memory import (
    MemoryLeadRepository,
    MemoryOpportunityRepository,
    MemoryStore,
    MemoryUnitOfWork,
)
from pycrmkit.tags import TagName, TagQuery
from pycrmkit.tasks import (
    TaskPriority,
    TaskQuery,
    TaskStatus,
    TaskUpdate,
)
from pycrmkit.timeline import TimelineEntryKind, TimelineProjector


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



def test_zero_to_hero_activities_mastery_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 16, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="guide-user",
        correlation_id="activities-guide-001",
    )

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

    occurred_at = datetime(2024, 1, 15, 9, 0, tzinfo=UTC)
    activity = crm.activities.log(
        type=ActivityType.MEETING,
        occurred_at=occurred_at,
        subject="  Imported   discovery meeting ",
        description="Historical customer discovery.",
        direction=ActivityDirection.OUTBOUND,
        duration_seconds=3600,
        participants=(
            ActivityParticipant(
                reference=contact_ref,
                role="  customer  ",
                is_primary=True,
            ),
        ),
        references=(organization_ref,),
        source="legacy-crm",
        external_id="meeting-2024-001",
        metadata={"channel": "video"},
    )

    assert activity.type is ActivityType.MEETING
    assert activity.occurred_at == occurred_at
    assert activity.created_at == clock.now()
    assert activity.occurred_at != activity.created_at
    assert activity.subject == "Imported discovery meeting"
    assert activity.participants[0].role == "customer"
    assert activity.direction is ActivityDirection.OUTBOUND

    updated = crm.activities.update(
        activity.id,
        ActivityUpdate(
            subject="Corrected discovery meeting",
            source="crm-ui",
        ),
    )
    assert updated.id == activity.id
    assert updated.created_at == activity.created_at
    assert updated.subject == "Corrected discovery meeting"
    assert updated.source == "crm-ui"

    page = crm.activities.list(
        ActivityQuery(
            type=ActivityType.MEETING,
            participant=contact_ref,
            reference=organization_ref,
            direction=ActivityDirection.OUTBOUND,
            source="CRM-UI",
            external_id="meeting-2024-001",
            occurred_from=datetime(2024, 1, 1, tzinfo=UTC),
            occurred_until=datetime(2024, 2, 1, tzinfo=UTC),
        ),
        OffsetPageRequest(limit=10),
    )
    assert page.items == (updated,)
    assert page.total == 1


def test_zero_to_hero_activities_ordering_and_window_examples() -> None:
    crm = CRM.memory()

    older = crm.activities.log(
        type="note",
        occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
        subject="Historical interaction",
    )
    newer = crm.activities.log(
        type="note",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        subject="Recent interaction",
    )

    page = crm.activities.list()
    assert page.items[:2] == (newer, older)

    january_2024 = crm.activities.list(
        ActivityQuery(
            occurred_from=datetime(2024, 1, 1, tzinfo=UTC),
            occurred_until=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert january_2024.items == (older,)


def test_zero_to_hero_activities_invariant_examples() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    contact_ref = EntityReference(
        kind="contact",
        id=contact.id,
    )

    with pytest.raises(ValidationError) as empty_activity:
        crm.activities.log(type="note")
    assert empty_activity.value.code == "activity.context.required"

    with pytest.raises(ValidationError) as negative_duration:
        crm.activities.log(
            type="call",
            subject="Invalid duration",
            duration_seconds=-1,
        )
    assert negative_duration.value.code == "activity.duration.invalid"

    duplicate_participant = ActivityParticipant(
        reference=contact_ref,
        role="customer",
    )
    with pytest.raises(ValidationError) as duplicate:
        crm.activities.log(
            type="meeting",
            subject="Duplicate participant",
            participants=(
                duplicate_participant,
                ActivityParticipant(
                    reference=contact_ref,
                    role="attendee",
                ),
            ),
        )
    assert duplicate.value.code == "activity.participant.duplicate"

    other_contact = crm.contacts.create(
        display_name="Charles Babbage",
    )
    other_ref = EntityReference(
        kind="contact",
        id=other_contact.id,
    )
    with pytest.raises(ValidationError) as multiple_primary:
        crm.activities.log(
            type="meeting",
            subject="Multiple primary participants",
            participants=(
                ActivityParticipant(
                    reference=contact_ref,
                    is_primary=True,
                ),
                ActivityParticipant(
                    reference=other_ref,
                    is_primary=True,
                ),
            ),
        )
    assert multiple_primary.value.code == "activity.participant.multiple_primary"

    with pytest.raises(ValidationError) as duplicate_reference:
        crm.activities.log(
            type="note",
            subject="Duplicate references",
            references=(
                contact_ref,
                contact_ref,
            ),
        )
    assert duplicate_reference.value.code == "activity.reference.duplicate"

    with pytest.raises(ValidationError) as invalid_window:
        ActivityQuery(
            occurred_from=datetime(2026, 2, 1, tzinfo=UTC),
            occurred_until=datetime(2026, 1, 1, tzinfo=UTC),
        )
    assert invalid_window.value.code == "activity.query.invalid_interval"

    with pytest.raises(ValueError, match="timezone-aware"):
        crm.activities.log(
            type="note",
            occurred_at=datetime(2026, 1, 1),
            subject="Naive timestamp",
        )



def test_zero_to_hero_tasks_mastery_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 10, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="guide-user",
        correlation_id="tasks-guide-001",
    )

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    contact_ref = EntityReference(
        kind="contact",
        id=contact.id,
    )

    task = crm.tasks.create(
        title="  Prepare   renewal proposal ",
        description="Prepare the Q4 renewal package.",
        priority=TaskPriority.HIGH,
        due_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        owner_id="sales-team",
        assignee_id="seller-7",
        references=(contact_ref,),
        source="manual",
        external_id="renewal-task-001",
    )

    assert task.title == "Prepare renewal proposal"
    assert task.status is TaskStatus.OPEN
    assert task.priority is TaskPriority.HIGH
    assert task.started_at is None

    started = crm.tasks.start(task.id)
    assert started.status is TaskStatus.IN_PROGRESS
    assert started.started_at == clock.now()

    clock.advance(timedelta(minutes=5))
    updated = crm.tasks.update(
        task.id,
        TaskUpdate(
            priority="urgent",
            assignee_id="seller-9",
        ),
    )
    assert updated.status is TaskStatus.IN_PROGRESS
    assert updated.started_at == started.started_at
    assert updated.priority is TaskPriority.URGENT
    assert updated.assignee_id == "seller-9"

    clock.advance(timedelta(minutes=5))
    completed = crm.tasks.complete(task.id)
    assert completed.status is TaskStatus.COMPLETED
    assert completed.completed_at == clock.now()
    assert completed.is_terminal is True

    corrected = crm.tasks.update(
        task.id,
        TaskUpdate(
            description="Corrected completion context",
        ),
    )
    assert corrected.status is TaskStatus.COMPLETED
    assert corrected.completed_at == completed.completed_at

    reopened = crm.tasks.reopen(task.id)
    assert reopened.status is TaskStatus.OPEN
    assert reopened.started_at is None
    assert reopened.completed_at is None
    assert reopened.cancelled_at is None

    page = crm.tasks.list(
        TaskQuery(
            status=TaskStatus.OPEN,
            priority=TaskPriority.URGENT,
            assignee_id=" seller-9 ",
            reference=contact_ref,
            source="MANUAL",
            external_id="renewal-task-001",
        ),
        OffsetPageRequest(limit=10),
    )
    assert page.items == (reopened,)
    assert page.total == 1


def test_zero_to_hero_tasks_overdue_and_ordering_examples() -> None:
    crm = CRM.memory()

    reference_contact = crm.contacts.create(
        display_name="Grace Hopper",
    )
    ref = EntityReference(
        kind="contact",
        id=reference_contact.id,
    )

    overdue_task = crm.tasks.create(
        title="Old follow-up",
        priority="high",
        due_at=datetime(2026, 9, 1, tzinfo=UTC),
        assignee_id="seller-7",
        references=(ref,),
    )
    future_task = crm.tasks.create(
        title="Future follow-up",
        priority="normal",
        due_at=datetime(2026, 11, 1, tzinfo=UTC),
        assignee_id="seller-7",
        references=(ref,),
    )
    undated = crm.tasks.create(
        title="Backlog research",
        assignee_id="seller-7",
        references=(ref,),
    )

    ordered = crm.tasks.list(
        TaskQuery(
            assignee_id="seller-7",
            reference=ref,
        )
    )
    assert ordered.items == (
        overdue_task,
        future_task,
        undated,
    )

    instant = datetime(2026, 9, 27, tzinfo=UTC)
    overdue = crm.tasks.list(
        TaskQuery(
            overdue_at=instant,
        )
    )
    assert overdue.items == (overdue_task,)
    assert overdue_task.is_overdue(instant) is True

    crm.tasks.complete(overdue_task.id)
    no_longer_overdue = crm.tasks.list(
        TaskQuery(
            overdue_at=instant,
        )
    )
    assert no_longer_overdue.total == 0


def test_zero_to_hero_tasks_invariant_examples() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 10, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock)

    with pytest.raises(ValidationError) as blank_title:
        crm.tasks.create(title="   ")
    assert blank_title.value.code == "task.title.required"

    with pytest.raises(ValidationError) as invalid_priority:
        crm.tasks.create(
            title="Invalid priority",
            priority="critical",
        )
    assert invalid_priority.value.code == "task.priority.invalid"

    contact = crm.contacts.create(display_name="Ada Lovelace")
    ref = EntityReference(kind="contact", id=contact.id)
    with pytest.raises(ValidationError) as duplicate_reference:
        crm.tasks.create(
            title="Duplicate references",
            references=(ref, ref),
        )
    assert duplicate_reference.value.code == "task.reference.duplicate"

    direct = crm.tasks.create(title="Direct completion")
    completed = crm.tasks.complete(direct.id)
    assert completed.status is TaskStatus.COMPLETED
    assert completed.started_at is None
    assert completed.completed_at is not None

    with pytest.raises(InvalidStateError) as complete_again:
        crm.tasks.complete(direct.id)
    assert complete_again.value.code == "task.transition.invalid"

    cancelled = crm.tasks.create(title="Cancellation cycle")
    cancelled = crm.tasks.cancel(cancelled.id)
    assert cancelled.status is TaskStatus.CANCELLED
    reopened = crm.tasks.reopen(cancelled.id)
    assert reopened.status is TaskStatus.OPEN
    assert reopened.cancelled_at is None

    with pytest.raises(InvalidStateError) as reopen_open:
        crm.tasks.reopen(cancelled.id)
    assert reopen_open.value.code == "task.transition.invalid"

    with pytest.raises(ValidationError) as invalid_due_window:
        TaskQuery(
            due_from=datetime(2026, 10, 1, tzinfo=UTC),
            due_until=datetime(2026, 10, 1, tzinfo=UTC),
        )
    assert invalid_due_window.value.code == "task.query.invalid_due_interval"

    before_creation = crm.tasks.create(title="Clock integrity")
    clock.set(datetime(2026, 9, 26, 10, 0, tzinfo=UTC))
    with pytest.raises(ValidationError) as transition_before_creation:
        crm.tasks.start(before_creation.id)
    assert transition_before_creation.value.code == "task.transition.before_creation"



def test_zero_to_hero_timeline_mastery_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 10, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="guide-user",
        correlation_id="timeline-guide-001",
    )

    contact = crm.contacts.create(display_name="Ada Lovelace")
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )
    contact_ref = EntityReference(kind="contact", id=contact.id)
    organization_ref = EntityReference(
        kind="organization",
        id=organization.id,
    )

    historical = crm.activities.log(
        type="meeting",
        occurred_at=datetime(2024, 1, 15, 9, 0, tzinfo=UTC),
        subject="Imported discovery meeting",
        participants=(
            ActivityParticipant(
                reference=contact_ref,
                is_primary=True,
            ),
        ),
        references=(organization_ref,),
        source="legacy-crm",
    )

    clock.advance(timedelta(hours=1))
    task = crm.tasks.create(
        title="Prepare renewal",
        priority="high",
        references=(contact_ref, organization_ref),
    )
    clock.advance(timedelta(hours=1))
    crm.tasks.start(task.id)
    started_at = clock.now()
    clock.advance(timedelta(hours=1))
    crm.tasks.complete(task.id)
    completed_at = clock.now()

    contact_history = crm.timeline.for_contact(contact.id)
    organization_history = crm.timeline.for_organization(organization.id)

    assert organization_history.items == contact_history.items
    assert [
        str(entry.event_type)
        for entry in contact_history.items
    ] == [
        "task.completed",
        "task.started",
        "task.created",
        "activity.created",
    ]
    assert contact_history.items[-1].occurred_at == historical.occurred_at
    assert contact_history.items[-1].actor_id == "guide-user"
    assert contact_history.items[-1].correlation_id == "timeline-guide-001"

    task_only = crm.timeline.for_contact(
        contact.id,
        kind=TimelineEntryKind.TASK,
    )
    assert task_only.total == 3

    completed_only = crm.timeline.for_contact(
        contact.id,
        kind=TimelineEntryKind.TASK,
        event_type="task.completed",
    )
    assert [str(entry.event_type) for entry in completed_only.items] == [
        "task.completed"
    ]

    middle = crm.timeline.for_contact(
        contact.id,
        occurred_from=started_at,
        occurred_until=completed_at,
    )
    assert [str(entry.event_type) for entry in middle.items] == [
        "task.started"
    ]

    first = crm.timeline.for_contact(
        contact.id,
        OffsetPageRequest(limit=1, offset=0),
        kind=TimelineEntryKind.TASK,
    )
    second = crm.timeline.for_contact(
        contact.id,
        OffsetPageRequest(limit=1, offset=1),
        kind=TimelineEntryKind.TASK,
    )
    assert first.total == 3
    assert first.has_next is True
    assert second.has_previous is True

    fetched = crm.timeline.get(contact_history.items[0].id)
    assert fetched == contact_history.items[0]


def test_zero_to_hero_timeline_ignores_generic_update_noise() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(display_name="Ada Lovelace")
    ref = EntityReference(kind="contact", id=contact.id)

    activity = crm.activities.log(
        type="note",
        subject="Initial note",
        references=(ref,),
    )
    task = crm.tasks.create(
        title="Prepare proposal",
        references=(ref,),
    )

    before = crm.timeline.for_contact(contact.id)
    assert {str(entry.event_type) for entry in before.items} == {
        "activity.created",
        "task.created",
    }

    crm.activities.update(
        activity.id,
        ActivityUpdate(subject="Corrected note"),
    )
    crm.tasks.update(
        task.id,
        TaskUpdate(priority="urgent"),
    )

    after = crm.timeline.for_contact(contact.id)
    assert after.items == before.items


def test_zero_to_hero_timeline_replay_is_idempotent_and_conflicts_fail() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 27, 12, 0, tzinfo=UTC))
    ids = UUID4Factory()
    reference = EntityReference(
        kind="contact",
        id=ids.new(ContactId),
    )

    with MemoryUnitOfWork(store) as uow:
        activity = ActivityService(
            uow.activities,
            id_factory=ids,
            clock=clock,
        ).log(
            type="note",
            subject="Replay-safe history",
            references=(reference,),
        )
        event = DomainEvent.create(
            id_factory=ids,
            clock=clock,
            type="activity.created",
            aggregate_type="activity",
            aggregate_id=activity.id,
        )
        projector = TimelineProjector(
            uow.timeline,
            activities=uow.activities,
            tasks=uow.tasks,
        )

        first = projector.project(event)
        second = projector.project(event)

        assert first is not None
        assert second == first
        page = uow.timeline.list_for_reference(
            reference,
            OffsetPageRequest(),
        )
        assert page.items == (first,)
        assert page.total == 1

        conflicting = replace(
            first,
            title="Conflicting replay content",
        )
        with pytest.raises(DuplicateError) as conflict:
            uow.timeline.append(conflicting)
        assert conflict.value.code == "timeline.projection.conflict"


def test_zero_to_hero_timeline_projection_rolls_back_atomically() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 27, 13, 0, tzinfo=UTC))
    ids = UUID4Factory()
    reference = EntityReference(
        kind="contact",
        id=ids.new(ContactId),
    )

    with MemoryUnitOfWork(store) as uow:
        activity = ActivityService(
            uow.activities,
            id_factory=ids,
            clock=clock,
        ).log(
            type="note",
            subject="Will roll back",
            references=(reference,),
        )
        event = DomainEvent.create(
            id_factory=ids,
            clock=clock,
            type="activity.created",
            aggregate_type="activity",
            aggregate_id=activity.id,
        )
        projected = TimelineProjector(
            uow.timeline,
            activities=uow.activities,
            tasks=uow.tasks,
        ).project(event)
        assert projected is not None
        assert uow.timeline.list_for_reference(
            reference,
            OffsetPageRequest(),
        ).total == 1
        uow.rollback()

    with MemoryUnitOfWork(store) as uow:
        assert uow.activities.list(
            ActivityQuery(),
            OffsetPageRequest(),
        ).total == 0
        assert uow.timeline.list_for_reference(
            reference,
            OffsetPageRequest(),
        ).total == 0


def test_zero_to_hero_timeline_invalid_window_example() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(display_name="Grace Hopper")

    with pytest.raises(ValidationError) as invalid_window:
        crm.timeline.for_contact(
            contact.id,
            occurred_from=datetime(2026, 10, 1, tzinfo=UTC),
            occurred_until=datetime(2026, 10, 1, tzinfo=UTC),
        )
    assert invalid_window.value.code == "timeline.query.invalid_interval"



def test_zero_to_hero_leads_facade_lifecycle_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 14, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="sales-user-42",
        correlation_id="lead-guide-001",
    )

    contact = crm.contacts.create(display_name="Ada Lovelace")
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )

    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="  partner   referral ",
    )

    assert lead.status is LeadStatus.NEW
    assert lead.source == "partner referral"
    assert lead.contact_id == contact.id
    assert lead.organization_id == organization.id

    clock.advance(timedelta(minutes=15))
    qualified = crm.leads.qualify(lead.id)

    assert qualified.status is LeadStatus.QUALIFIED
    assert qualified.updated_at == clock.now()

    clock.advance(timedelta(minutes=15))
    disqualified = crm.leads.disqualify(lead.id)

    assert disqualified.status is LeadStatus.DISQUALIFIED

    with pytest.raises(InvalidStateError) as invalid_transition:
        crm.leads.qualify(lead.id)
    assert invalid_transition.value.code == "lead.transition.invalid"


def test_zero_to_hero_leads_service_states_and_queries_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 15, 0, tzinfo=UTC))
    ids = UUID4Factory()
    repository = MemoryLeadRepository()
    service = LeadService(
        repository,
        id_factory=ids,
        clock=clock,
    )
    contact_id = ids.new(ContactId)

    lead = service.create(
        contact_id=contact_id,
        source="  Partner   Referral ",
    )
    assert lead.status is LeadStatus.NEW
    assert lead.source == "Partner Referral"

    clock.advance(timedelta(minutes=5))
    opened = service.open(lead.id)
    assert opened.status is LeadStatus.OPEN

    clock.advance(timedelta(minutes=5))
    contacted = service.mark_contacted(lead.id)
    assert contacted.status is LeadStatus.CONTACTED

    page = service.list(
        LeadQuery(
            status=LeadStatus.CONTACTED,
            contact_id=contact_id,
            source=" partner referral ",
        ),
        OffsetPageRequest(limit=10, offset=0),
    )

    assert page.items == (contacted,)
    assert page.total == 1
    assert page.has_next is False
    assert service.get(lead.id) == contacted

    terminal = service.disqualify(lead.id)
    assert terminal.status is LeadStatus.DISQUALIFIED

    with pytest.raises(InvalidStateError) as invalid_transition:
        service.qualify(lead.id)
    assert invalid_transition.value.code == "lead.transition.invalid"


def test_zero_to_hero_leads_validation_example() -> None:
    ids = UUID4Factory()
    service = LeadService(
        MemoryLeadRepository(),
        id_factory=ids,
        clock=FixedClock(datetime(2026, 9, 27, 16, 0, tzinfo=UTC)),
    )

    with pytest.raises(ValidationError) as source_too_long:
        service.create(
            contact_id=ids.new(ContactId),
            source="x" * 121,
        )
    assert source_too_long.value.code == "lead.source.too_long"



def test_zero_to_hero_opportunities_facade_value_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 17, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="sales-user-42",
        correlation_id="opportunity-guide-001",
    )

    contact = crm.contacts.create(display_name="Ada Lovelace")
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )

    opportunity = crm.opportunities.create(
        name="  Enterprise   renewal ",
        contact_id=contact.id,
        organization_id=organization.id,
        estimated_value=Decimal("25000.00"),
        currency=" eur ",
        probability=Decimal("0.65"),
        expected_close_date=date(2026, 12, 31),
        owner_id=" seller-42 ",
    )

    assert opportunity.name == "Enterprise renewal"
    assert opportunity.status is OpportunityStatus.OPEN
    assert opportunity.money is not None
    assert opportunity.money.amount == Decimal("25000.00")
    assert opportunity.money.currency == "EUR"
    assert opportunity.probability == Decimal("0.65")
    assert opportunity.owner_id == "seller-42"
    assert opportunity.organization_id == organization.id


def test_zero_to_hero_opportunities_service_query_and_lifecycle_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 18, 0, tzinfo=UTC))
    ids = UUID4Factory()
    repository = MemoryOpportunityRepository()
    service = OpportunityService(
        repository,
        id_factory=ids,
        clock=clock,
    )
    contact_id = ids.new(ContactId)

    opportunity = service.create(
        name="Enterprise expansion",
        contact_id=contact_id,
        estimated_value=Decimal("40000"),
        currency="EUR",
        probability=Decimal("0.40"),
        expected_close_date=date(2027, 1, 31),
        owner_id="Seller-42",
    )

    page = service.list(
        OpportunityQuery(
            status=OpportunityStatus.OPEN,
            contact_id=contact_id,
            currency="eur",
            owner_id="seller-42",
            expected_close_date=date(2027, 1, 31),
        ),
        OffsetPageRequest(limit=10, offset=0),
    )

    assert page.items == (opportunity,)
    assert page.total == 1
    assert page.has_next is False
    assert service.get(opportunity.id) == opportunity

    clock.advance(timedelta(hours=1))
    won = service.mark_won(opportunity.id)

    assert won.status is OpportunityStatus.WON
    assert won.is_terminal is True
    assert won.updated_at == clock.now()

    with pytest.raises(InvalidStateError) as invalid_transition:
        service.mark_lost(opportunity.id)
    assert invalid_transition.value.code == "opportunity.transition.invalid"


def test_zero_to_hero_opportunities_validation_examples() -> None:
    ids = UUID4Factory()
    service = OpportunityService(
        MemoryOpportunityRepository(),
        id_factory=ids,
        clock=FixedClock(datetime(2026, 9, 27, 19, 0, tzinfo=UTC)),
    )
    contact_id = ids.new(ContactId)

    with pytest.raises(ValidationError) as missing_currency:
        service.create(
            name="Missing currency",
            contact_id=contact_id,
            estimated_value=Decimal("1000"),
        )
    assert missing_currency.value.code == "opportunity.currency.required"

    with pytest.raises(ValidationError) as invalid_probability:
        service.create(
            name="Float probability",
            contact_id=contact_id,
            probability=0.5,  # type: ignore[arg-type]
        )
    assert invalid_probability.value.code == "opportunity.probability.decimal_required"

    with pytest.raises(ValidationError) as stage_without_pipeline:
        service.create(
            name="Stage without pipeline",
            contact_id=contact_id,
            stage_id="proposal",
        )
    assert stage_without_pipeline.value.code == "opportunity.stage_id.pipeline_required"



def test_zero_to_hero_pipelines_facade_and_movement_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 20, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="sales-user-42",
        correlation_id="pipeline-guide-001",
    )

    pipeline = crm.pipelines.define(
        id=" SALES ",
        name="Enterprise Sales",
        stages=(
            Stage("proposal", "Proposal", 20, Decimal("0.65")),
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.35")),
            Stage("won", "Won", 90, terminal=True, outcome="won"),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "proposal"),
            StageTransition("proposal", "won"),
        ),
    )

    assert pipeline.id == "sales"
    assert tuple(stage.id for stage in pipeline.stages) == (
        "new",
        "qualified",
        "proposal",
        "won",
    )
    assert pipeline.initial_stage.id == "new"
    assert pipeline.stage(" QUALIFIED ").default_probability == Decimal("0.35")
    assert pipeline.allows("new", "qualified") is True
    assert pipeline.allows("new", "won") is False
    assert crm.pipelines.get(" SALES ") == pipeline

    page = crm.pipelines.list(OffsetPageRequest(limit=10, offset=0))
    assert page.items == (pipeline,)
    assert page.total == 1

    contact = crm.contacts.create(display_name="Ada Lovelace")
    opportunity = crm.opportunities.create(
        name="Enterprise renewal",
        contact_id=contact.id,
        pipeline_id=pipeline.id,
        stage_id="new",
    )

    assert opportunity.stage_entered_at == opportunity.created_at
    assert opportunity.probability is None

    clock.advance(timedelta(hours=1))
    opportunity = crm.opportunities.move(opportunity.id, to="qualified")
    assert opportunity.stage_id == "qualified"
    assert opportunity.probability == Decimal("0.35")
    assert opportunity.stage_duration(clock.now()) == timedelta(0)

    clock.advance(timedelta(hours=1))
    assert opportunity.stage_duration(clock.now()) == timedelta(hours=1)
    opportunity = crm.opportunities.move(opportunity.id, to="proposal")
    assert opportunity.probability == Decimal("0.65")

    clock.advance(timedelta(hours=1))
    opportunity = crm.opportunities.move(opportunity.id, to="won")
    assert opportunity.status is OpportunityStatus.WON
    assert opportunity.probability == Decimal("1")
    assert opportunity.is_terminal is True

    with pytest.raises(InvalidStateError) as closed:
        crm.opportunities.move(opportunity.id, to="proposal")
    assert closed.value.code == "opportunity.stage.transition.closed"


def test_zero_to_hero_pipelines_policy_and_unassigned_entry_example() -> None:
    pipeline = Pipeline(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.35")),
            Stage("won", "Won", 90, terminal=True, outcome=StageOutcome.WON),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "won"),
        ),
    )

    initial = PipelineTransitionPolicy.resolve(
        pipeline,
        from_stage=None,
        to_stage="new",
    )
    assert initial.id == "new"

    target = PipelineTransitionPolicy.resolve(
        pipeline,
        from_stage="new",
        to_stage="qualified",
    )
    assert target.id == "qualified"
    assert target.default_probability == Decimal("0.35")

    with pytest.raises(InvalidStageTransition) as skip_initial:
        PipelineTransitionPolicy.resolve(
            pipeline,
            from_stage=None,
            to_stage="qualified",
        )
    assert skip_initial.value.code == "pipeline.transition.invalid"

    with pytest.raises(InvalidStageTransition) as undeclared:
        PipelineTransitionPolicy.resolve(
            pipeline,
            from_stage="new",
            to_stage="won",
        )
    assert undeclared.value.code == "pipeline.transition.invalid"


def test_zero_to_hero_pipelines_validation_examples() -> None:
    with pytest.raises(ValidationError) as probability_mismatch:
        Stage(
            "won",
            "Won",
            90,
            Decimal("0.80"),
            terminal=True,
            outcome="won",
        )
    assert (
        probability_mismatch.value.code
        == "pipeline.stage.probability.terminal_mismatch"
    )

    with pytest.raises(InvalidStageTransition) as self_transition:
        StageTransition("proposal", "proposal")
    assert self_transition.value.code == "pipeline.transition.invalid"

    with pytest.raises(ValidationError) as outgoing_terminal:
        Pipeline(
            id="sales",
            name="Sales",
            stages=(
                Stage("won", "Won", 90, terminal=True, outcome="won"),
                Stage("other", "Other", 100),
            ),
            transitions=(
                StageTransition("won", "other"),
            ),
        )
    assert outgoing_terminal.value.code == "pipeline.transition.from_terminal"


def test_zero_to_hero_pipelines_duplicate_definition_example() -> None:
    crm = CRM.memory()
    stages = (Stage("new", "New", 0),)

    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=stages,
    )

    with pytest.raises(DuplicateError) as duplicate:
        crm.pipelines.define(
            id=" SALES ",
            name="Another Sales",
            stages=stages,
        )
    assert duplicate.value.code == "pipeline.duplicate"
