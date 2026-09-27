"""Executable examples for the V1 Zero-to-Hero guides."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import StringIO

import pytest

from pycrmkit import CRM, CRMContext, __version__
from pycrmkit.activities import (
    ActivityDirection,
    ActivityParticipant,
    ActivityQuery,
    ActivityService,
    ActivityType,
    ActivityUpdate,
)
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationRecipient,
    EmailDeliveryEventType,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderResult,
)
from pycrmkit.contacts import (
    Address,
    ContactEmail,
    ContactId,
    ContactPhone,
    ContactQuery,
    ContactService,
    ContactStatus,
    ContactUpdate,
)
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.custom_fields import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldDefinitionQuery,
    CustomFieldDefinitionRevision,
    CustomFieldOption,
    CustomFieldType,
    CustomFieldValue,
    CustomFieldValueId,
)
from pycrmkit.dedup import (
    CandidateRecord,
    ConflictSeverity,
    DedupConflict,
    DedupDecision,
    DeduplicationEngine,
    DedupProfile,
    DedupProvenance,
    DedupScorePolicy,
    DedupSignal,
    InMemoryCandidateSource,
    MergePolicy,
    MergeResolution,
    MergeService,
    SignalMatch,
    StandardConflictDetector,
    StandardSignalMatcher,
    merge_contact_profile,
)
from pycrmkit.events import (
    DomainEvent,
    EventRegistry,
    EventSerializer,
    InProcessEventBus,
    default_event_registry,
)
from pycrmkit.exceptions import (
    ConflictError,
    DuplicateError,
    IntegrationError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from pycrmkit.external_identities import (
    ExternalIdentityService,
    normalize_external_id,
    normalize_external_system,
)
from pycrmkit.importers import (
    CompositeValidator,
    CSVReader,
    DuplicateResult,
    FieldMapping,
    ImportPipeline,
    ImportRow,
    IterableReader,
    JSONLReader,
    JSONReader,
    NormalizationRule,
    PersistAction,
    PersistResult,
    PredicateValidator,
    RecordMapper,
    RecordNormalizer,
    RequiredFieldsValidator,
    casefold_text,
    compose_normalizers,
    strip_text,
)
from pycrmkit.leads import LeadConversionService, LeadQuery, LeadService, LeadStatus
from pycrmkit.opportunities import (
    OpportunityQuery,
    OpportunityService,
    OpportunityStatus,
)
from pycrmkit.organizations import (
    OrganizationAddress,
    OrganizationDomain,
    OrganizationQuery,
    OrganizationStatus,
    OrganizationUpdate,
)
from pycrmkit.pipelines import (
    InvalidStageTransition,
    Pipeline,
    PipelineTransitionPolicy,
    Stage,
    StageOutcome,
    StageTransition,
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
    MemoryPipelineRepository,
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
from pycrmkit.webhooks import (
    WebhookDeliveryState,
    WebhookRequest,
    WebhookResponse,
    WebhookRetryPolicy,
    sign_webhook_payload,
    verify_webhook_signature,
)


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

    with pytest.raises(InvalidStageTransition) as closed:
        crm.opportunities.move(opportunity.id, to="proposal")
    assert closed.value.code == "pipeline.transition.invalid"


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



def test_zero_to_hero_lead_conversion_facade_atomic_idempotent_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 21, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="seller-42",
        correlation_id="conversion-guide-001",
    )

    contact = crm.contacts.create(display_name="Ada Lovelace")
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )
    pipeline = crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.35")),
        ),
        transitions=(
            StageTransition("new", "qualified"),
        ),
    )
    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    lead = crm.leads.qualify(lead.id)

    created_events: list[DomainEvent] = []
    converted_events: list[DomainEvent] = []
    crm.events.subscribe("opportunity.created", created_events.append)
    crm.events.subscribe("lead.converted", converted_events.append)

    first = crm.leads.convert(
        lead.id,
        name="  Enterprise   rollout ",
        estimated_value=Decimal("25000.00"),
        currency=" eur ",
        pipeline_id=pipeline.id,
        expected_close_date=date(2027, 1, 31),
        owner_id=" seller-42 ",
        idempotency_key="convert-001",
    )
    retry = crm.leads.convert(
        lead.id,
        name="Enterprise rollout",
        estimated_value=Decimal("25000.0"),
        currency="EUR",
        pipeline_id=" SALES ",
        expected_close_date=date(2027, 1, 31),
        owner_id="seller-42",
        idempotency_key="convert-001",
    )

    assert retry.id == first.id
    assert first.contact_id == contact.id
    assert first.organization_id == organization.id
    assert first.pipeline_id == "sales"
    assert first.stage_id == "new"
    assert first.probability == Decimal("0.10")
    assert first.currency == "EUR"
    assert len(created_events) == 1
    assert len(converted_events) == 1

    with crm._runtime.uow_factory() as uow:
        persisted_lead = uow.leads.get(lead.id)
        opportunities = uow.opportunities.list(
            OpportunityQuery(contact_id=contact.id),
            OffsetPageRequest(),
        )

    assert persisted_lead.status is LeadStatus.CONVERTED
    assert persisted_lead.converted_opportunity_id == first.id
    assert opportunities.total == 1

    actions = [
        entry.action
        for entry in crm.audit.by_correlation("conversion-guide-001").items
    ]
    assert actions.count("opportunity.created") == 1
    assert actions.count("lead.converted") == 1


def test_zero_to_hero_lead_conversion_service_replay_semantics_example() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 22, 0, tzinfo=UTC))
    ids = UUID4Factory()
    leads = MemoryLeadRepository()
    opportunities = MemoryOpportunityRepository()
    pipelines = MemoryPipelineRepository()

    lead_service = LeadService(
        leads,
        id_factory=ids,
        clock=clock,
    )
    lead = lead_service.create(
        contact_id=ids.new(ContactId),
    )
    lead = lead_service.qualify(lead.id)

    conversion = LeadConversionService(
        leads=leads,
        opportunities=opportunities,
        pipelines=pipelines,
        id_factory=ids,
        clock=clock,
    )

    first = conversion.convert(
        lead.id,
        estimated_value=Decimal("25000.00"),
        currency="eur",
        idempotency_key="retry-key",
    )
    retry = conversion.convert(
        lead.id,
        estimated_value=Decimal("25000.0"),
        currency="EUR",
        idempotency_key="retry-key",
    )

    assert first.created is True
    assert retry.created is False
    assert retry.opportunity.id == first.opportunity.id

    with pytest.raises(ConflictError) as conflict:
        conversion.convert(
            lead.id,
            estimated_value=Decimal("30000"),
            currency="EUR",
            idempotency_key="retry-key",
        )
    assert conflict.value.code == "lead.conversion.idempotency_conflict"

    with pytest.raises(InvalidStateError) as different_key:
        conversion.convert(
            lead.id,
            estimated_value=Decimal("25000"),
            currency="EUR",
            idempotency_key="another-key",
        )
    assert different_key.value.code == "lead.conversion.already_converted"


def test_zero_to_hero_lead_conversion_invalid_request_rolls_back_example() -> None:
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 27, 23, 0, tzinfo=UTC))
    )
    contact = crm.contacts.create(display_name="Katherine Johnson")
    lead = crm.leads.create(contact_id=contact.id)
    lead = crm.leads.qualify(lead.id)

    with pytest.raises(ValidationError) as invalid_currency:
        crm.leads.convert(
            lead.id,
            estimated_value=Decimal("10000"),
            currency="EU",
            idempotency_key="bad-currency",
        )
    assert invalid_currency.value.code == "money.currency.invalid"

    with crm._runtime.uow_factory() as uow:
        persisted_lead = uow.leads.get(lead.id)
        opportunities = uow.opportunities.list(
            OpportunityQuery(contact_id=contact.id),
            OffsetPageRequest(),
        )

    assert persisted_lead.status is LeadStatus.QUALIFIED
    assert persisted_lead.converted_opportunity_id is None
    assert opportunities.total == 0


def test_zero_to_hero_lead_conversion_post_commit_retry_example() -> None:
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 0, 0, tzinfo=UTC))
    )
    contact = crm.contacts.create(display_name="Grace Hopper")
    lead = crm.leads.create(contact_id=contact.id)
    lead = crm.leads.qualify(lead.id)

    def fail_after_commit(event: DomainEvent) -> None:
        del event
        raise RuntimeError("simulated transport failure")

    crm.events.subscribe("opportunity.created", fail_after_commit)

    with pytest.raises(RuntimeError, match="simulated transport failure"):
        crm.leads.convert(
            lead.id,
            estimated_value=Decimal("15000.00"),
            currency="eur",
            idempotency_key="transport-retry",
        )

    crm.events.unsubscribe("opportunity.created", fail_after_commit)

    opportunity = crm.leads.convert(
        lead.id,
        estimated_value=Decimal("15000.0"),
        currency="EUR",
        idempotency_key="transport-retry",
    )

    with crm._runtime.uow_factory() as uow:
        persisted_lead = uow.leads.get(lead.id)
        opportunities = uow.opportunities.list(
            OpportunityQuery(contact_id=contact.id),
            OffsetPageRequest(),
        )

    assert persisted_lead.status is LeadStatus.CONVERTED
    assert persisted_lead.converted_opportunity_id == opportunity.id
    assert opportunities.total == 1
    assert opportunities.items[0].id == opportunity.id



class _ZeroToHeroAcceptingEmailProvider:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> EmailProviderResult:
        self.messages.append(message)
        return EmailProviderResult(
            provider="guide-fake",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="guide-provider-001",
            provider_metadata={"request_id": "guide-request-001"},
        )


class _ZeroToHeroFailingEmailProvider:
    def send(self, message: EmailMessage) -> EmailProviderResult:
        del message
        return EmailProviderResult(
            provider="guide-fake",
            status=EmailDeliveryStatus.FAILED,
            failure_code="guide.rejected",
        )


def test_zero_to_hero_email_direct_send_history_and_idempotency_example() -> None:
    provider = _ZeroToHeroAcceptingEmailProvider()
    clock = FixedClock(datetime(2026, 9, 28, 8, 0, tzinfo=UTC))
    crm = CRM.memory(
        clock=clock,
        email_provider=provider,
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.com",
        ),
    ).with_context(
        actor_id="seller-42",
        correlation_id="email-guide-001",
    )

    contact = crm.contacts.create(display_name="Ada Lovelace")
    reference = EntityReference("contact", contact.id)
    recipient = CommunicationRecipient(
        CommunicationAddress(
            CommunicationChannel.EMAIL,
            "Ada@Example.COM",
        ),
        display_name="  Ada   Lovelace ",
        reference=reference,
    )
    content = CommunicationContent(
        subject="  Enterprise   proposal ",
        text_body="Your proposal is ready.",
    )

    first = crm.email.send(
        to=(recipient,),
        content=content,
        idempotency_key="proposal-001",
    )
    retry = crm.email.send(
        to=(recipient,),
        content=content,
        idempotency_key="proposal-001",
    )

    assert retry.id == first.id
    assert len(provider.messages) == 1
    assert provider.messages[0].sender.normalized == "sales@example.com"
    assert provider.messages[0].recipients[0].address.normalized == "ada@example.com"
    assert first.subject == "Enterprise proposal"
    assert first.delivery_status is EmailDeliveryEventType.SENT
    assert first.external_id == "guide-provider-001"
    assert crm.email.get(first.id) == first
    assert crm.email.for_contact(contact.id).items == (first,)

    history = crm.email.delivery_history(first.id)
    assert history.total == 2
    assert {item.event_type for item in history.items} == {
        EmailDeliveryEventType.QUEUED,
        EmailDeliveryEventType.SENT,
    }


def test_zero_to_hero_email_callbacks_replay_timeline_and_out_of_order_example() -> None:
    provider = _ZeroToHeroAcceptingEmailProvider()
    clock = FixedClock(datetime(2026, 9, 28, 9, 0, tzinfo=UTC))
    crm = CRM.memory(
        clock=clock,
        email_provider=provider,
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.com",
        ),
    )
    contact = crm.contacts.create(display_name="Grace Hopper")
    reference = EntityReference("contact", contact.id)

    published: list[DomainEvent] = []
    for event_name in (
        "email.queued",
        "email.sent",
        "email.delivered",
        "email.opened",
    ):
        crm.events.subscribe(event_name, published.append)

    record = crm.email.send(
        to=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "grace@example.com",
                ),
                reference=reference,
            ),
        ),
        content=CommunicationContent(
            subject="Follow-up",
            text_body="Hello Grace.",
        ),
    )

    clock.advance(timedelta(minutes=4))
    opened = crm.email.record_delivery_event(
        provider="guide-fake",
        provider_message_id="guide-provider-001",
        event_type=EmailDeliveryEventType.OPENED,
        occurred_at=clock.now(),
        external_event_id="evt-opened-001",
    )

    clock.advance(timedelta(minutes=1))
    late_delivered = crm.email.record_delivery_event(
        provider="guide-fake",
        provider_message_id="guide-provider-001",
        event_type=EmailDeliveryEventType.DELIVERED,
        occurred_at=datetime(2026, 9, 28, 9, 3, tzinfo=UTC),
        external_event_id="evt-delivered-late",
    )

    before_replay = crm.email.delivery_history(record.id).total
    replay = crm.email.record_delivery_event(
        provider="guide-fake",
        provider_message_id="guide-provider-001",
        event_type=EmailDeliveryEventType.OPENED,
        occurred_at=datetime(2026, 9, 28, 9, 4, tzinfo=UTC),
        external_event_id="evt-opened-001",
    )
    after_replay = crm.email.delivery_history(record.id).total

    assert replay.id == opened.id
    assert late_delivered.event_type is EmailDeliveryEventType.DELIVERED
    assert after_replay == before_replay

    current = crm.email.get(record.id)
    assert current.delivery_status is EmailDeliveryEventType.OPENED
    assert current.last_delivery_event_at == datetime(
        2026,
        9,
        28,
        9,
        4,
        tzinfo=UTC,
    )

    history_types = {
        item.event_type
        for item in crm.email.delivery_history(record.id).items
    }
    assert {
        EmailDeliveryEventType.QUEUED,
        EmailDeliveryEventType.SENT,
        EmailDeliveryEventType.OPENED,
        EmailDeliveryEventType.DELIVERED,
    } <= history_types

    timeline = crm.timeline.for_contact(
        contact.id,
        kind=TimelineEntryKind.COMMUNICATION,
    )
    timeline_types = {
        str(item.event_type)
        for item in timeline.items
    }
    assert {
        "email.queued",
        "email.sent",
        "email.opened",
        "email.delivered",
    } <= timeline_types

    event_types = [str(event.type) for event in published]
    assert event_types.count("email.opened") == 1
    assert all("grace@example.com" not in repr(event.payload) for event in published)


def test_zero_to_hero_email_provider_failure_is_normalized_example() -> None:
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 10, 0, tzinfo=UTC)),
        email_provider=_ZeroToHeroFailingEmailProvider(),
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.com",
        ),
    )
    contact = crm.contacts.create(display_name="Failure Contact")
    reference = EntityReference("contact", contact.id)

    record = crm.email.send(
        to=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "failure@example.com",
                ),
                reference=reference,
            ),
        ),
        content=CommunicationContent(
            subject="Failure path",
            text_body="Body",
        ),
    )

    assert record.delivery_status is EmailDeliveryEventType.FAILED
    assert record.external_id is None

    history = crm.email.delivery_history(record.id)
    failed = next(
        item
        for item in history.items
        if item.event_type is EmailDeliveryEventType.FAILED
    )
    assert failed.failure_code == "guide.rejected"


def test_zero_to_hero_email_configuration_and_content_validation_examples() -> None:
    recipient = CommunicationRecipient(
        CommunicationAddress(
            CommunicationChannel.EMAIL,
            "ada@example.com",
        ),
    )
    content = CommunicationContent(text_body="Hello.")

    without_provider = CRM.memory(
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.com",
        ),
    )
    with pytest.raises(IntegrationError) as missing_provider:
        without_provider.email.send(
            to=(recipient,),
            content=content,
        )
    assert missing_provider.value.code == "communication.email.provider.required"

    provider = _ZeroToHeroAcceptingEmailProvider()
    without_sender = CRM.memory(email_provider=provider)
    with pytest.raises(ValidationError) as missing_sender:
        without_sender.email.send(
            to=(recipient,),
            content=content,
        )
    assert missing_sender.value.code == "communication.email.sender.required"

    configured = CRM.memory(
        email_provider=provider,
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.com",
        ),
    )
    with pytest.raises(ValidationError) as invalid_choice:
        configured.email.send(
            to=(recipient,),
        )
    assert invalid_choice.value.code == "communication.email.content.choice_invalid"



def test_zero_to_hero_domain_event_envelope_registry_and_serializer_example() -> None:
    clock = FixedClock(datetime(2026, 9, 28, 11, 0, tzinfo=UTC))
    event = DomainEvent.create(
        id_factory=UUID4Factory(),
        clock=clock,
        type=" Contact.Created ",
        aggregate_type=" Contact ",
        aggregate_id=" contact-123 ",
        actor_id=" agent-7 ",
        correlation_id=" request-900 ",
        payload={
            "source": "guide",
            "labels": ["vip", "new"],
        },
        metadata={"origin": "zero-to-hero"},
    )

    assert str(event.type) == "contact.created"
    assert event.schema_version == 1
    assert event.aggregate_type == "contact"
    assert event.aggregate_id == "contact-123"
    assert event.occurred_at == clock.now()
    assert event.actor_id == "agent-7"
    assert event.correlation_id == "request-900"
    assert event.payload["labels"] == ("vip", "new")

    registry = EventRegistry()
    v1 = registry.register("contact.created", 1)
    v2 = registry.register("CONTACT.CREATED", 2)

    assert registry.resolve("contact.created", 1) == v1
    assert registry.latest("contact.created") == v2
    assert registry.supports("contact.created", 1)
    assert registry.definitions() == (v1, v2)

    serializer = EventSerializer(registry)
    encoded = serializer.dumps(event)
    restored = serializer.loads(encoded)

    assert encoded == json.dumps(
        event.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert restored.to_dict() == event.to_dict()

    unsupported = DomainEvent.create(
        id_factory=UUID4Factory(),
        clock=clock,
        type="contact.updated",
        aggregate_type="contact",
        aggregate_id="contact-123",
    )
    with pytest.raises(NotFoundError) as unknown:
        serializer.dumps(unsupported)
    assert unknown.value.code == "event.registry.definition.not_found"

    builtins = default_event_registry()
    assert len(builtins) == 41
    assert builtins.supports("email.delivered", 1)


def test_zero_to_hero_domain_event_bus_exact_order_and_subscription_example() -> None:
    bus = InProcessEventBus()
    clock = FixedClock(datetime(2026, 9, 28, 12, 0, tzinfo=UTC))
    ids = UUID4Factory()
    calls: list[str] = []

    def first(event: DomainEvent) -> None:
        calls.append(f"first:{event.type}")

    def second(event: DomainEvent) -> None:
        calls.append(f"second:{event.type}")

    bus.subscribe("contact.created", first)
    bus.subscribe("contact.created", first)
    bus.subscribe("contact.created", second)

    created = DomainEvent.create(
        id_factory=ids,
        clock=clock,
        type="contact.created",
        aggregate_type="contact",
        aggregate_id="contact-1",
    )
    updated = DomainEvent.create(
        id_factory=ids,
        clock=clock,
        type="contact.updated",
        aggregate_type="contact",
        aggregate_id="contact-1",
    )

    bus.publish(created)
    bus.publish(updated)

    assert calls == [
        "first:contact.created",
        "second:contact.created",
    ]
    assert bus.unsubscribe("contact.created", first) is True
    assert bus.unsubscribe("contact.created", first) is False


def test_zero_to_hero_domain_event_correlation_and_causation_example() -> None:
    clock = FixedClock(datetime(2026, 9, 28, 13, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="agent-7",
        correlation_id="request-900",
    )

    root_events: list[DomainEvent] = []
    child_events: list[DomainEvent] = []
    grandchild_events: list[DomainEvent] = []

    crm.events.subscribe("contact.created", root_events.append)
    crm.events.subscribe("task.created", child_events.append)
    crm.events.subscribe("task.completed", grandchild_events.append)

    crm.contacts.create(display_name="Trace Root")
    root = root_events[0]

    task = crm.with_event(root).tasks.create(title="Follow up")
    child = child_events[0]

    crm.with_event(child).tasks.complete(task.id)
    grandchild = grandchild_events[0]

    assert root.actor_id == "agent-7"
    assert root.correlation_id == "request-900"
    assert root.causation_id is None

    assert child.actor_id == "agent-7"
    assert child.correlation_id == "request-900"
    assert child.causation_id == root.id

    assert grandchild.actor_id == "agent-7"
    assert grandchild.correlation_id == "request-900"
    assert grandchild.causation_id == child.id

    parent_without_correlation = DomainEvent.create(
        id_factory=UUID4Factory(),
        clock=clock,
        type="contact.created",
        aggregate_type="contact",
        aggregate_id="uncorrelated",
    )
    context = CRMContext.from_event(parent_without_correlation)
    assert context.correlation_id == str(parent_without_correlation.id)
    assert context.causation_id == parent_without_correlation.id


def test_zero_to_hero_domain_event_post_commit_subscriber_semantics_example() -> None:
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 14, 0, tzinfo=UTC))
    )
    observed_totals: list[int] = []

    def observe_committed_state(event: DomainEvent) -> None:
        del event
        observed_totals.append(
            crm.contacts.search(
                ContactQuery(name="Committed Contact")
            ).total
        )

    def fail_after_commit(event: DomainEvent) -> None:
        del event
        raise RuntimeError("subscriber failed after commit")

    crm.events.subscribe("contact.created", observe_committed_state)
    crm.events.subscribe("contact.created", fail_after_commit)

    with pytest.raises(RuntimeError, match="subscriber failed after commit"):
        crm.contacts.create(display_name="Committed Contact")

    assert observed_totals == [1]
    assert (
        crm.contacts.search(
            ContactQuery(name="Committed Contact")
        ).total
        == 1
    )



class _ZeroToHeroWebhookSequenceTransport:
    def __init__(self, responses: list[WebhookResponse]) -> None:
        self.responses = responses
        self.requests: list[WebhookRequest] = []

    def send(self, request: WebhookRequest) -> WebhookResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def test_zero_to_hero_webhooks_auto_delivery_retry_signature_and_idempotency() -> None:
    secret = "0123456789abcdef0123456789abcdef"
    clock = FixedClock(datetime(2026, 9, 28, 15, 0, tzinfo=UTC))
    transport = _ZeroToHeroWebhookSequenceTransport(
        [
            WebhookResponse(503),
            WebhookResponse(204),
        ]
    )
    crm = CRM.memory(
        clock=clock,
        webhook_transport=transport,
        webhook_retry_policy=WebhookRetryPolicy(max_attempts=2),
    )
    subscription = crm.webhooks.register(
        url=" HTTPS://Hooks.Example.COM/crm ",
        events=("contact.created",),
        signing_secret=secret,
    )
    observed: list[DomainEvent] = []
    crm.events.subscribe("contact.created", observed.append)

    contact = crm.contacts.create(display_name="Webhook Guide")

    assert crm.contacts.get(contact.id) == contact
    assert subscription.url == "https://hooks.example.com/crm"
    assert len(observed) == 1
    event = observed[0]

    history = crm.webhooks.deliveries(event_id=event.id)
    assert history.total == 1
    first = history.items[0]
    assert first.subscription_id == subscription.id
    assert first.state is WebhookDeliveryState.RETRY_SCHEDULED
    assert first.attempt_count == 1
    assert first.last_status_code == 503
    assert len(transport.requests) == 1

    first_request = transport.requests[0]
    timestamp = int(first_request.headers["X-PyCRMKit-Timestamp"])
    assert verify_webhook_signature(
        secret,
        timestamp,
        first_request.body,
        first_request.headers["X-PyCRMKit-Signature"],
    )

    assert crm.webhooks.retry_due() == ()
    clock.advance(timedelta(seconds=10))
    retried = crm.webhooks.retry_due()

    assert len(retried) == 1
    final = retried[0]
    assert final.id == first.id
    assert final.state is WebhookDeliveryState.SUCCEEDED
    assert final.attempt_count == 2
    assert len(transport.requests) == 2
    assert (
        transport.requests[0].headers["X-PyCRMKit-Idempotency-Key"]
        == transport.requests[1].headers["X-PyCRMKit-Idempotency-Key"]
    )

    attempts = crm.webhooks.attempts(final.id)
    assert [attempt.status_code for attempt in attempts.items] == [503, 204]
    assert [attempt.outcome.value for attempt in attempts.items] == [
        "retry_scheduled",
        "succeeded",
    ]

    replay = crm.webhooks.deliver(event)
    assert replay[0].id == final.id
    assert len(transport.requests) == 2


def test_zero_to_hero_webhooks_manual_delivery_when_auto_bridge_is_disabled() -> None:
    transport = _ZeroToHeroWebhookSequenceTransport([WebhookResponse(202)])
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 16, 0, tzinfo=UTC)),
        webhook_transport=transport,
        webhook_auto_delivery=False,
    )
    crm.webhooks.register(
        url="https://hooks.example.com/manual",
        events=("contact.created",),
        signing_secret="0123456789abcdef0123456789abcdef",
    )
    observed: list[DomainEvent] = []
    crm.events.subscribe("contact.created", observed.append)

    crm.contacts.create(display_name="Manual Webhook")

    assert len(observed) == 1
    assert crm.webhooks.deliveries().total == 0
    assert transport.requests == []

    delivered = crm.webhooks.deliver(observed[0])

    assert len(delivered) == 1
    assert delivered[0].state is WebhookDeliveryState.SUCCEEDED
    assert len(transport.requests) == 1


def test_zero_to_hero_webhooks_non_retryable_response_dead_letters() -> None:
    transport = _ZeroToHeroWebhookSequenceTransport([WebhookResponse(400)])
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 17, 0, tzinfo=UTC)),
        webhook_transport=transport,
    )
    crm.webhooks.register(
        url="https://hooks.example.com/dead-letter",
        events=("contact.created",),
        signing_secret="0123456789abcdef0123456789abcdef",
    )
    observed: list[DomainEvent] = []
    crm.events.subscribe("contact.created", observed.append)

    crm.contacts.create(display_name="Dead Letter")

    delivery = crm.webhooks.deliveries(event_id=observed[0].id).items[0]
    assert delivery.state is WebhookDeliveryState.DEAD_LETTER
    assert delivery.attempt_count == 1
    assert delivery.last_status_code == 400
    assert delivery.last_error_code == "webhook.http.400"
    assert delivery.next_attempt_at is None
    assert len(transport.requests) == 1

    replay = crm.webhooks.deliver(observed[0])
    assert replay[0].id == delivery.id
    assert len(transport.requests) == 1


def test_zero_to_hero_webhooks_disabled_subscription_dead_letters_due_retry() -> None:
    clock = FixedClock(datetime(2026, 9, 28, 18, 0, tzinfo=UTC))
    transport = _ZeroToHeroWebhookSequenceTransport([WebhookResponse(503)])
    crm = CRM.memory(
        clock=clock,
        webhook_transport=transport,
        webhook_retry_policy=WebhookRetryPolicy(max_attempts=3),
    )
    subscription = crm.webhooks.register(
        url="https://hooks.example.com/disable-before-retry",
        events=("contact.created",),
        signing_secret="0123456789abcdef0123456789abcdef",
    )
    observed: list[DomainEvent] = []
    crm.events.subscribe("contact.created", observed.append)

    crm.contacts.create(display_name="Disable Before Retry")

    scheduled = crm.webhooks.deliveries(event_id=observed[0].id).items[0]
    assert scheduled.state is WebhookDeliveryState.RETRY_SCHEDULED
    assert len(transport.requests) == 1

    crm.webhooks.disable(subscription.id)
    clock.advance(timedelta(seconds=10))
    retried = crm.webhooks.retry_due()

    assert len(retried) == 1
    final = retried[0]
    assert final.id == scheduled.id
    assert final.state is WebhookDeliveryState.DEAD_LETTER
    assert final.last_error_code == "webhook.subscription_disabled"
    assert len(transport.requests) == 1

    attempts = crm.webhooks.attempts(final.id)
    assert [attempt.outcome.value for attempt in attempts.items] == [
        "retry_scheduled",
        "dead_letter",
    ]


def test_zero_to_hero_webhooks_secret_rotation_and_freshness_example() -> None:
    old_secret = "0123456789abcdef0123456789abcdef"
    new_secret = "fedcba9876543210fedcba9876543210"
    now = datetime(2026, 9, 28, 19, 0, tzinfo=UTC)
    crm = CRM.memory(
        clock=FixedClock(now),
        webhook_auto_delivery=False,
    ).with_context(
        actor_id="security-admin",
        correlation_id="webhook-rotation-guide",
    )
    subscription = crm.webhooks.register(
        url="https://hooks.example.com/security",
        events=("contact.created",),
        signing_secret=old_secret,
    )

    rotated = crm.webhooks.rotate_secret(
        subscription.id,
        signing_secret=new_secret,
    )

    assert rotated.signing_secret == new_secret

    payload = b'{"type":"contact.created"}'
    timestamp = int(now.timestamp())
    old_signature = sign_webhook_payload(
        old_secret,
        timestamp,
        payload,
    )
    new_signature = sign_webhook_payload(
        new_secret,
        timestamp,
        payload,
    )

    assert not verify_webhook_signature(
        rotated.signing_secret,
        timestamp,
        payload,
        old_signature,
    )
    assert verify_webhook_signature(
        rotated.signing_secret,
        timestamp,
        payload,
        new_signature,
        current_timestamp=timestamp + 300,
        tolerance_seconds=300,
    )
    assert not verify_webhook_signature(
        rotated.signing_secret,
        timestamp,
        payload,
        new_signature,
        current_timestamp=timestamp + 301,
        tolerance_seconds=300,
    )

    audit = crm.audit.by_correlation("webhook-rotation-guide")
    actions = [entry.action for entry in audit.items]
    assert actions.count("webhook.subscription.secret_rotated") == 1
    audit_text = repr(tuple(entry.changes for entry in audit.items))
    assert old_secret not in audit_text
    assert new_secret not in audit_text



def test_zero_to_hero_external_identity_normalization_replay_and_listing_example() -> None:
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 20, 0, tzinfo=UTC)),
        webhook_auto_delivery=False,
    )
    contact = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
    )
    attached_events: list[DomainEvent] = []
    crm.events.subscribe(
        "external_identity.attached",
        attached_events.append,
    )

    first = crm.external_identities.attach(
        contact,
        system=" HubSpot CRM ",
        external_id="  AbC-123  ",
        metadata={"portal": "eu"},
    )
    replay = crm.external_identities.attach(
        contact,
        system="hubspot-crm",
        external_id="AbC-123",
        metadata={"portal": "us"},
    )

    assert normalize_external_system(" HubSpot CRM ") == "hubspot_crm"
    assert normalize_external_id("  AbC-123  ") == "AbC-123"
    assert first.system == "hubspot_crm"
    assert first.external_id == "AbC-123"
    assert first.entity == EntityReference("contact", contact.id)
    assert replay.id == first.id
    assert replay.metadata == {"portal": "eu"}
    assert len(attached_events) == 1
    assert dict(attached_events[0].payload) == {"system": "hubspot_crm"}

    salesforce = crm.external_identities.attach(
        contact,
        system="salesforce",
        external_id="003XYZ",
    )
    page = crm.external_identities.list_for_entity(
        contact,
        OffsetPageRequest(limit=10, offset=0),
    )

    assert page.total == 2
    assert page.items == (first, salesforce)
    assert crm.external_identities.resolve(
        "HUBSPOT CRM",
        "AbC-123",
    ) == first


def test_zero_to_hero_external_identity_global_ownership_and_case_example() -> None:
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 21, 0, tzinfo=UTC)),
        webhook_auto_delivery=False,
    )
    first_contact = crm.contacts.create(display_name="First Owner")
    second_contact = crm.contacts.create(display_name="Second Owner")

    identity = crm.external_identities.attach(
        first_contact,
        system="legacy_crm",
        external_id="AbC-123",
    )

    with pytest.raises(NotFoundError) as different_case:
        crm.external_identities.resolve(
            "legacy_crm",
            "abc-123",
        )
    assert different_case.value.code == "external_identity.not_found"
    assert "abc-123" not in repr(different_case.value.context)

    with pytest.raises(ConflictError) as conflict:
        crm.external_identities.attach(
            second_contact,
            system="LEGACY CRM",
            external_id="AbC-123",
        )

    assert conflict.value.code == "external_identity.owner.conflict"
    assert conflict.value.context["system"] == "legacy_crm"
    assert conflict.value.context["owner_type"] == "contact"
    assert conflict.value.context["owner_id"] == str(first_contact.id)
    assert identity.entity.id == first_contact.id


def test_zero_to_hero_external_identity_detach_and_event_privacy_example() -> None:
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 22, 0, tzinfo=UTC)),
        webhook_auto_delivery=False,
    )
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )
    events: list[DomainEvent] = []
    crm.events.subscribe(
        "external_identity.attached",
        events.append,
    )
    crm.events.subscribe(
        "external_identity.detached",
        events.append,
    )

    external_id = "customer-secret-000042"
    crm.external_identities.attach(
        organization,
        system="Legacy CRM",
        external_id=external_id,
    )

    assert crm.external_identities.detach(
        "legacy-crm",
        external_id,
    ) is True
    assert crm.external_identities.detach(
        "legacy_crm",
        external_id,
    ) is False

    assert [str(event.type) for event in events] == [
        "external_identity.attached",
        "external_identity.detached",
    ]
    for event in events:
        assert event.aggregate_type == "organization"
        assert event.aggregate_id == str(organization.id)
        assert dict(event.payload) == {"system": "legacy_crm"}
        assert external_id not in repr(event.payload)


def test_zero_to_hero_external_identity_generic_reference_boundary_example() -> None:
    crm = CRM.memory(
        clock=FixedClock(datetime(2026, 9, 28, 23, 0, tzinfo=UTC)),
        webhook_auto_delivery=False,
    )
    contact = crm.contacts.create(display_name="UUID Source")
    generic_reference = EntityReference(
        "custom-entity",
        contact.id,
    )

    identity = crm.external_identities.attach(
        generic_reference,
        system="external-platform",
        external_id="custom-42",
        metadata={"kind": "integration-only"},
    )

    assert identity.entity.kind == "custom_entity"
    assert identity.entity.id == contact.id
    assert crm.external_identities.resolve(
        "external platform",
        "custom-42",
    ) == identity

    with pytest.raises(TypeError):
        crm.external_identities.attach(
            object(),  # type: ignore[arg-type]
            system="external_platform",
            external_id="invalid-target",
        )



class _ZeroToHeroImportDuplicateDetector:
    def detect(self, row: ImportRow) -> DuplicateResult:
        if row.values.get("email") == "duplicate@example.com":
            return DuplicateResult.match(
                existing_entity_id="contact-existing",
                reason="normalized email",
            )
        return DuplicateResult.no_match()


class _ZeroToHeroImportRecordingPersister:
    def __init__(self) -> None:
        self.rows: list[ImportRow] = []

    def persist(self, row: ImportRow) -> PersistResult:
        self.rows.append(row)
        if row.values.get("email") == "update@example.com":
            return PersistResult(
                PersistAction.UPDATED,
                entity_id="contact-update",
            )
        return PersistResult(
            PersistAction.CREATED,
            entity_id=f"contact-{row.number}",
        )


def _zero_to_hero_looks_like_email(value: object) -> bool:
    return isinstance(value, str) and "@" in value


def test_zero_to_hero_import_pipeline_mixed_outcomes_example() -> None:
    persister = _ZeroToHeroImportRecordingPersister()
    pipeline = ImportPipeline(
        reader=IterableReader(
            (
                {"Email": " New@Example.COM ", "Name": "New"},
                {"Email": " update@example.com ", "Name": "Update"},
                {"Email": " DUPLICATE@example.com ", "Name": "Duplicate"},
                {"Email": "invalid", "Name": " "},
            )
        ),
        mapper=RecordMapper(
            (
                FieldMapping("Email", "email"),
                FieldMapping("Name", "display_name"),
            )
        ),
        normalizer=RecordNormalizer(
            (
                NormalizationRule(
                    "email",
                    compose_normalizers(
                        strip_text,
                        casefold_text,
                    ),
                ),
                NormalizationRule("display_name", strip_text),
            )
        ),
        validator=CompositeValidator(
            (
                RequiredFieldsValidator(("email", "display_name")),
                PredicateValidator(
                    field="email",
                    predicate=_zero_to_hero_looks_like_email,
                    code="guide.import.email.invalid",
                    message="email must contain @",
                ),
            )
        ),
        deduplicator=_ZeroToHeroImportDuplicateDetector(),
        persister=persister,
    )

    report = pipeline.run()

    assert report.as_dict() == {
        "rows_read": 4,
        "rows_created": 1,
        "rows_updated": 1,
        "rows_skipped": 2,
        "duplicates": 1,
        "validation_errors": 2,
    }
    assert [row.values["email"] for row in persister.rows] == [
        "new@example.com",
        "update@example.com",
    ]
    assert report.row_results[2].duplicate is True
    assert report.row_results[2].duplicate_entity_id == "contact-existing"
    assert [error.code for error in report.row_results[3].errors] == [
        "import.required.missing",
        "guide.import.email.invalid",
    ]
    assert all(
        error.stage.value == "validate"
        for error in report.row_results[3].errors
    )


def test_zero_to_hero_import_readers_csv_json_jsonl_example() -> None:
    csv_rows = list(
        CSVReader(
            StringIO(
                "email,name,city\n"
                "ada@example.com,Ada,Paris\n"
                "zoe@example.com,Zoé,\n"
            )
        ).read()
    )
    assert csv_rows == [
        {"email": "ada@example.com", "name": "Ada", "city": "Paris"},
        {"email": "zoe@example.com", "name": "Zoé", "city": ""},
    ]

    json_rows = list(
        JSONReader(
            StringIO(
                '[{"email":"ada@example.com","custom":{"tier":1}},'
                '{"email":"ada@example.com","custom":{"tier":1}}]'
            )
        ).read()
    )
    assert json_rows[0]["custom"] == {"tier": 1}
    assert json_rows[1] == json_rows[0]

    jsonl_rows = list(
        JSONLReader(
            StringIO(
                '{"email":"ada@example.com"}\n'
                '\n'
                '{"email":"grace@example.com"}\n'
            )
        ).read()
    )
    assert jsonl_rows == [
        {"email": "ada@example.com"},
        {"email": "grace@example.com"},
    ]


def test_zero_to_hero_import_summary_mode_keeps_exact_counters_example() -> None:
    row_count = 250
    persister = _ZeroToHeroImportRecordingPersister()
    records = (
        {
            "email": f"user-{index}@example.com",
            "display_name": f"User {index}",
        }
        for index in range(row_count)
    )
    report = ImportPipeline(
        reader=IterableReader(records),
        persister=persister,
        retain_row_results=False,
    ).run()

    assert report.as_dict() == {
        "rows_read": row_count,
        "rows_created": row_count,
        "rows_updated": 0,
        "rows_skipped": 0,
        "duplicates": 0,
        "validation_errors": 0,
    }
    assert report.row_results == []
    assert report.errors == ()
    assert len(persister.rows) == row_count


class _ZeroToHeroImportFailingPersister:
    def persist(self, row: ImportRow) -> PersistResult:
        raise RuntimeError(f"persistence failed for row {row.number}")


def test_zero_to_hero_import_structural_and_persistence_failures_propagate() -> None:
    with pytest.raises(ValidationError) as malformed_json:
        list(JSONReader(StringIO('[{"email":}')).read())
    assert malformed_json.value.code == "import.json.syntax.invalid"

    pipeline = ImportPipeline(
        reader=IterableReader(({"email": "ada@example.com"},)),
        persister=_ZeroToHeroImportFailingPersister(),
    )

    with pytest.raises(RuntimeError, match="persistence failed for row 1"):
        pipeline.run()


def _zero_to_hero_import_text(row: ImportRow, field: str) -> str:
    value = row.values.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


class _ZeroToHeroExternalContactPersister:
    def __init__(self, store: MemoryStore, clock: FixedClock) -> None:
        self.store = store
        self.clock = clock

    def persist(self, row: ImportRow) -> PersistResult:
        system = _zero_to_hero_import_text(row, "system")
        external_id = _zero_to_hero_import_text(row, "external_id")
        display_name = _zero_to_hero_import_text(row, "display_name")
        email = _zero_to_hero_import_text(row, "email")

        with MemoryUnitOfWork(self.store) as uow:
            identities = ExternalIdentityService(
                uow.external_identities,
                clock=self.clock,
            )
            existing = identities.find(system, external_id)
            if existing is not None:
                return PersistResult(
                    PersistAction.SKIPPED,
                    entity_id=str(existing.entity_id),
                )

            contact = ContactService(
                uow.contacts,
                clock=self.clock,
            ).create(
                display_name=display_name,
                emails=(
                    ContactEmail(
                        email,
                        is_primary=True,
                    ),
                ),
                source="zero-to-hero-import",
            )
            identities.attach(
                EntityReference(
                    "contact",
                    contact.id,
                ),
                system=system,
                external_id=external_id,
                metadata={"source": "guide"},
            )
            uow.commit()

        return PersistResult(
            PersistAction.CREATED,
            entity_id=str(contact.id),
        )


def test_zero_to_hero_import_external_identity_same_uow_replay_example() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 28, 23, 30, tzinfo=UTC))
    persister = _ZeroToHeroExternalContactPersister(store, clock)
    records = (
        {
            "system": "legacy_crm",
            "external_id": "ADA-42",
            "display_name": "Ada Lovelace",
            "email": "ada@example.com",
        },
    )

    first = ImportPipeline(
        reader=IterableReader(records),
        persister=persister,
    ).run()
    second = ImportPipeline(
        reader=IterableReader(records),
        persister=persister,
    ).run()

    assert first.rows_created == 1
    assert first.rows_skipped == 0
    assert second.rows_created == 0
    assert second.rows_skipped == 1

    with MemoryUnitOfWork(store) as uow:
        contacts = uow.contacts.search(
            ContactQuery(),
            OffsetPageRequest(),
        )
        identity = uow.external_identities.find(
            "legacy_crm",
            "ADA-42",
        )

    assert contacts.total == 1
    assert identity is not None
    assert identity.entity_type == "contact"
    assert str(identity.entity_id) == first.row_results[0].entity_id
    assert second.row_results[0].entity_id == first.row_results[0].entity_id



def test_zero_to_hero_dedup_profile_and_all_signals_example() -> None:
    incoming = DedupProfile.from_mapping(
        {
            "email": " Ada@Example.COM ",
            "phone": "+33 (6) 12 34 56 78",
            "first_name": " Ada ",
            "last_name": " LOVELACE ",
            "organization": " Analytical Engines ",
            "address": {
                "line1": " 10 Rue des Mathématiques ",
                "postal_code": "75001",
                "city": " Paris ",
                "country_code": "FR",
            },
            "external_identity": {
                "system": "HubSpot",
                "external_id": " Contact-42 ",
            },
            "custom_identifiers": {
                "customer_number": " C-001 ",
            },
        }
    )
    candidate = DedupProfile.from_mapping(
        {
            "normalized_email": "ada@example.com",
            "normalized_phone": "+33612345678",
            "display_name": "ADA LOVELACE",
            "company": "analytical engines",
            "address": {
                "line1": "10 rue des mathématiques",
                "postal_code": "75001",
                "city": "paris",
                "country_code": "fr",
            },
            "external_identities": (
                {
                    "system": "hubspot",
                    "external_id": "Contact-42",
                },
            ),
            "custom_identifiers": {
                "CUSTOMER_NUMBER": "C-001",
            },
        }
    )

    matches = StandardSignalMatcher().match(incoming, candidate)

    assert incoming.emails == frozenset({"ada@example.com"})
    assert incoming.phones == frozenset({"+33612345678"})
    assert incoming.full_name == "ada lovelace"
    assert incoming.organization == "analytical engines"
    assert incoming.addresses == frozenset(
        {"10 rue des mathématiques|75001|paris|fr"}
    )
    assert incoming.external_identities == frozenset(
        {("hubspot", "Contact-42")}
    )
    assert incoming.custom_identifiers == frozenset(
        {("customer_number", "C-001")}
    )
    assert {match.signal for match in matches} == set(DedupSignal)


def test_zero_to_hero_dedup_scoring_unique_signal_and_ordering_example() -> None:
    duplicate_profile = {
        "email": "ada@example.com",
        "full_name": "Ada Lovelace",
        "organization": "Analytical Engines",
    }
    engine = DeduplicationEngine(
        InMemoryCandidateSource(
            (
                CandidateRecord("contact-c", duplicate_profile),
                CandidateRecord(
                    "contact-b",
                    {"email": "ada@example.com"},
                ),
                CandidateRecord("contact-a", duplicate_profile),
            )
        )
    )
    row = ImportRow(
        1,
        {
            "email": "ADA@EXAMPLE.COM",
            "display_name": "ada lovelace",
            "company": "analytical engines",
        },
    )

    assessments = engine.evaluate(row)

    assert [
        (item.candidate.entity_id, item.score, item.decision)
        for item in assessments
    ] == [
        ("contact-a", 100, DedupDecision.DUPLICATE),
        ("contact-c", 100, DedupDecision.DUPLICATE),
        ("contact-b", 70, DedupDecision.REVIEW),
    ]

    repeated_email_score = DedupScorePolicy().evaluate(
        (
            SignalMatch(DedupSignal.EMAIL, "ada@example.com"),
            SignalMatch(DedupSignal.EMAIL, "ada+work@example.com"),
        )
    )
    assert repeated_email_score.score == 70
    assert repeated_email_score.decision is DedupDecision.REVIEW

    custom_policy = DedupScorePolicy(
        review_threshold=60,
        duplicate_threshold=80,
    )
    custom_result = custom_policy.evaluate(
        (
            SignalMatch(DedupSignal.PHONE, "+33612345678"),
            SignalMatch(DedupSignal.FULL_NAME, "ada lovelace"),
        )
    )
    assert custom_result.score == 85
    assert custom_result.decision is DedupDecision.DUPLICATE


def test_zero_to_hero_dedup_warning_and_blocking_conflict_example() -> None:
    warning_incoming = DedupProfile.from_mapping(
        {
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "organization": "Analytical Engines",
            "phone": "+33611111111",
        }
    )
    warning_candidate = DedupProfile.from_mapping(
        {
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "organization": "Analytical Engines",
            "phone": "+33622222222",
        }
    )
    matcher = StandardSignalMatcher()
    detector = StandardConflictDetector()
    policy = DedupScorePolicy()

    warning_matches = matcher.match(
        warning_incoming,
        warning_candidate,
    )
    warning_conflicts = detector.detect(
        warning_incoming,
        warning_candidate,
    )
    warning_result = policy.evaluate(
        warning_matches,
        warning_conflicts,
    )

    assert warning_result.score == 100
    assert warning_result.decision is DedupDecision.DUPLICATE
    assert len(warning_conflicts) == 1
    assert warning_conflicts[0].signal is DedupSignal.PHONE
    assert warning_conflicts[0].severity is ConflictSeverity.WARNING

    blocking_incoming = DedupProfile.from_mapping(
        {
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "organization": "Analytical Engines",
            "custom_identifiers": {
                "customer_number": "C-001",
            },
        }
    )
    blocking_candidate = DedupProfile.from_mapping(
        {
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "organization": "Analytical Engines",
            "custom_identifiers": {
                "customer_number": "C-999",
            },
        }
    )
    blocking_matches = matcher.match(
        blocking_incoming,
        blocking_candidate,
    )
    blocking_conflicts = detector.detect(
        blocking_incoming,
        blocking_candidate,
    )
    blocking_result = policy.evaluate(
        blocking_matches,
        blocking_conflicts,
    )

    assert blocking_result.score == 100
    assert blocking_result.decision is DedupDecision.CONFLICT
    assert any(
        conflict.signal is DedupSignal.CUSTOM_IDENTIFIER
        and conflict.severity is ConflictSeverity.BLOCKING
        for conflict in blocking_conflicts
    )


def test_zero_to_hero_dedup_ambiguous_duplicate_is_not_auto_selected() -> None:
    record = {
        "email": "ada@example.com",
        "full_name": "Ada Lovelace",
        "organization": "Analytical Engines",
    }
    engine = DeduplicationEngine(
        InMemoryCandidateSource(
            (
                CandidateRecord("contact-1", record),
                CandidateRecord("contact-2", record),
            )
        )
    )
    row = ImportRow(1, record)

    assessments = engine.evaluate(row)
    detected = engine.detect(row)

    assert len(assessments) == 2
    assert all(
        item.decision is DedupDecision.DUPLICATE
        for item in assessments
    )
    assert detected.is_duplicate is False
    assert detected.existing_entity_id is None
    assert assessments[0].provenance.as_dict()["decision"] == "duplicate"


def test_zero_to_hero_dedup_import_pipeline_unique_duplicate_example() -> None:
    deduplicator = DeduplicationEngine(
        InMemoryCandidateSource(
            (
                CandidateRecord(
                    "contact-existing",
                    {
                        "email": "ada@example.com",
                        "full_name": "Ada Lovelace",
                        "organization": "Analytical Engines",
                    },
                ),
            )
        )
    )
    persister = _ZeroToHeroImportRecordingPersister()
    report = ImportPipeline(
        reader=IterableReader(
            (
                {
                    "email": "ADA@EXAMPLE.COM",
                    "full_name": "Ada Lovelace",
                    "organization": "Analytical Engines",
                },
                {
                    "email": "grace@example.com",
                    "full_name": "Grace Hopper",
                    "organization": "US Navy",
                },
            )
        ),
        deduplicator=deduplicator,
        persister=persister,
    ).run()

    assert report.as_dict() == {
        "rows_read": 2,
        "rows_created": 1,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 1,
        "validation_errors": 0,
    }
    assert report.row_results[0].duplicate is True
    assert report.row_results[0].duplicate_entity_id == "contact-existing"
    assert [row.values["email"] for row in persister.rows] == [
        "grace@example.com",
    ]



def _zero_to_hero_merge_provenance(
    duplicate_id: ContactId,
    *,
    decision: DedupDecision = DedupDecision.DUPLICATE,
) -> DedupProvenance:
    return DedupProvenance(
        candidate_entity_id=str(duplicate_id),
        score=100 if decision is DedupDecision.DUPLICATE else 70,
        decision=decision,
        matches=(
            SignalMatch(
                DedupSignal.EMAIL,
                "ada@example.com",
            ),
        ),
    )


def test_zero_to_hero_contact_merge_profile_policy_example() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 28, 8, tzinfo=UTC))

    with MemoryUnitOfWork(store) as uow:
        service = ContactService(
            uow.contacts,
            clock=clock,
        )
        primary = service.create(
            display_name="Ada Primary",
            emails=(
                ContactEmail(
                    "ada@example.com",
                    is_primary=True,
                ),
            ),
        )
        duplicate = service.create(
            display_name="Ada Duplicate",
            emails=(
                ContactEmail(
                    "ada.alt@example.com",
                    is_primary=True,
                ),
            ),
        )

    with pytest.raises(ConflictError) as conflict:
        merge_contact_profile(
            primary,
            duplicate,
            at=clock.now(),
            policy=MergePolicy(),
        )
    assert conflict.value.code == "merge.contact.email_primary.conflict"

    merged = merge_contact_profile(
        primary,
        duplicate,
        at=clock.now(),
        policy=MergePolicy(
            primary_email_conflict=MergeResolution.KEEP_DUPLICATE,
        ),
    )

    assert {email.normalized for email in merged.emails} == {
        "ada@example.com",
        "ada.alt@example.com",
    }
    assert [
        email.normalized
        for email in merged.emails
        if email.is_primary
    ] == ["ada.alt@example.com"]


def test_zero_to_hero_contact_merge_provenance_safeguards_example() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 28, 9, tzinfo=UTC))
    service = MergeService(
        lambda: MemoryUnitOfWork(store),
        clock=clock,
    )
    id_factory = UUID4Factory()
    primary_id = id_factory.new(ContactId)
    duplicate_id = id_factory.new(ContactId)

    with pytest.raises(ValidationError) as missing:
        service.merge_contacts(
            primary_id=primary_id,
            duplicate_id=duplicate_id,
        )
    assert missing.value.code == "merge.provenance.required"

    blocking = DedupProvenance(
        candidate_entity_id=str(duplicate_id),
        score=100,
        decision=DedupDecision.DUPLICATE,
        matches=(),
        conflicts=(
            DedupConflict(
                signal=DedupSignal.CUSTOM_IDENTIFIER,
                severity=ConflictSeverity.BLOCKING,
                key="customer_number",
                incoming_values=("C-001",),
                candidate_values=("C-999",),
            ),
        ),
    )

    with pytest.raises(ConflictError) as blocked:
        service.merge_contacts(
            primary_id=primary_id,
            duplicate_id=duplicate_id,
            provenance=blocking,
        )
    assert blocked.value.code == "merge.provenance.blocking_conflict"
    assert blocked.value.context == {
        "signals": ("custom_identifier",),
    }


def test_zero_to_hero_contact_merge_manual_policy_example() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 28, 10, tzinfo=UTC))

    with MemoryUnitOfWork(store) as uow:
        contacts = ContactService(
            uow.contacts,
            clock=clock,
        )
        primary = contacts.create(
            display_name="Manual Primary",
            emails=(
                ContactEmail(
                    "manual@example.com",
                    is_primary=True,
                ),
            ),
        )
        duplicate = contacts.create(
            display_name="Manual Duplicate",
            emails=(
                ContactEmail(
                    "MANUAL@example.com",
                    is_primary=True,
                ),
            ),
        )
        uow.commit()

    clock.advance(timedelta(minutes=5))
    result = MergeService(
        lambda: MemoryUnitOfWork(store),
        clock=clock,
        policy=MergePolicy(
            require_duplicate_provenance=False,
        ),
    ).merge_contacts(
        primary_id=primary.id,
        duplicate_id=duplicate.id,
        actor_id="manual-reviewer",
    )

    assert result.primary.id == primary.id
    assert result.duplicate.status is ContactStatus.ARCHIVED
    assert result.provenance is None
    assert "provenance" not in result.audit_entry.changes


def test_zero_to_hero_contact_merge_external_identity_and_audit_example() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 28, 11, tzinfo=UTC))

    with MemoryUnitOfWork(store) as uow:
        contacts = ContactService(
            uow.contacts,
            clock=clock,
        )
        primary = contacts.create(
            last_name="Lovelace",
            emails=(
                ContactEmail(
                    "ada@example.com",
                    is_primary=True,
                ),
            ),
            metadata={"owner_note": "primary"},
        )
        duplicate = contacts.create(
            first_name="Ada",
            emails=(
                ContactEmail(
                    "ADA@EXAMPLE.COM",
                    is_primary=True,
                ),
            ),
            phones=(
                ContactPhone(
                    "+33 6 12 34 56 78",
                    is_primary=True,
                ),
            ),
            metadata={"import_batch": "guide-20"},
        )
        ExternalIdentityService(
            uow.external_identities,
            clock=clock,
        ).attach(
            EntityReference(
                "contact",
                duplicate.id,
            ),
            system="hubspot",
            external_id="Contact-42",
            metadata={"source": "guide"},
        )
        uow.commit()

    clock.advance(timedelta(minutes=10))
    provenance = _zero_to_hero_merge_provenance(
        duplicate.id,
    )
    result = MergeService(
        lambda: MemoryUnitOfWork(store),
        clock=clock,
    ).merge_contacts(
        primary_id=primary.id,
        duplicate_id=duplicate.id,
        provenance=provenance,
        actor_id="guide-operator",
        correlation_id="guide-merge-001",
    )

    assert result.primary.first_name == "Ada"
    assert result.primary.last_name == "Lovelace"
    assert result.primary.display_name == "Ada Lovelace"
    assert result.primary.phones[0].normalized == "+33612345678"
    assert result.primary.metadata == {
        "import_batch": "guide-20",
        "owner_note": "primary",
    }
    assert result.duplicate.status is ContactStatus.ARCHIVED
    assert result.statistics.external_identities_moved == 1
    assert result.audit_entry.action == "contact.merged"
    assert result.audit_entry.actor_id == "guide-operator"
    assert result.audit_entry.correlation_id == "guide-merge-001"
    assert result.audit_entry.changes["duplicate_id"] == str(duplicate.id)
    assert "ada@example.com" not in repr(result.audit_entry.changes)
    assert result.provenance is provenance
    assert result.provenance.matches[0].value == "ada@example.com"

    with MemoryUnitOfWork(store) as uow:
        identity = uow.external_identities.find(
            "hubspot",
            "Contact-42",
        )
        audit = uow.audit.list_for_entity(
            "contact",
            str(primary.id),
            OffsetPageRequest(),
        )

    assert identity is not None
    assert identity.entity_id == primary.id
    assert audit.total == 1


def test_zero_to_hero_contact_merge_rollback_on_custom_field_conflict() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 28, 12, tzinfo=UTC))
    id_factory = UUID4Factory()

    with MemoryUnitOfWork(store) as uow:
        contacts = ContactService(
            uow.contacts,
            clock=clock,
        )
        primary = contacts.create(
            display_name="Rollback Primary",
            emails=(
                ContactEmail(
                    "rollback@example.com",
                    is_primary=True,
                ),
            ),
        )
        duplicate = contacts.create(
            display_name="Rollback Duplicate",
            emails=(
                ContactEmail(
                    "ROLLBACK@example.com",
                    is_primary=True,
                ),
            ),
            phones=(
                ContactPhone(
                    "+33 6 99 99 99 99",
                    is_primary=True,
                ),
            ),
        )
        primary_ref = EntityReference(
            "contact",
            primary.id,
        )
        duplicate_ref = EntityReference(
            "contact",
            duplicate.id,
        )
        definition_id = id_factory.new(
            CustomFieldDefinitionId
        )
        uow.custom_fields.save_definition(
            CustomFieldDefinition(
                id=definition_id,
                created_at=clock.now(),
                updated_at=clock.now(),
                key="tier",
                label="Tier",
                field_type=CustomFieldType.STRING,
                schema_version=1,
                applies_to=("contact",),
            )
        )
        uow.custom_fields.save_value(
            CustomFieldValue(
                id=id_factory.new(
                    CustomFieldValueId
                ),
                created_at=clock.now(),
                updated_at=clock.now(),
                definition_id=definition_id,
                entity=primary_ref,
                schema_version=1,
                value="gold",
            )
        )
        uow.custom_fields.save_value(
            CustomFieldValue(
                id=id_factory.new(
                    CustomFieldValueId
                ),
                created_at=clock.now(),
                updated_at=clock.now(),
                definition_id=definition_id,
                entity=duplicate_ref,
                schema_version=1,
                value="silver",
            )
        )
        uow.commit()

    clock.advance(timedelta(minutes=10))
    with pytest.raises(ConflictError) as conflict:
        MergeService(
            lambda: MemoryUnitOfWork(store),
            clock=clock,
        ).merge_contacts(
            primary_id=primary.id,
            duplicate_id=duplicate.id,
            provenance=_zero_to_hero_merge_provenance(
                duplicate.id
            ),
        )
    assert conflict.value.code == "merge.custom_field.conflict"

    with MemoryUnitOfWork(store) as uow:
        stored_primary = uow.contacts.get(primary.id)
        stored_duplicate = uow.contacts.get(duplicate.id)
        primary_value = uow.custom_fields.get_value(
            definition_id,
            primary_ref,
        )
        duplicate_value = uow.custom_fields.get_value(
            definition_id,
            duplicate_ref,
        )
        audit = uow.audit.list_for_entity(
            "contact",
            str(primary.id),
            OffsetPageRequest(),
        )

    assert stored_primary.phones == ()
    assert stored_duplicate.status is ContactStatus.ACTIVE
    assert primary_value.value == "gold"
    assert duplicate_value.value == "silver"
    assert audit.total == 0
