"""Transactional merge execution across CRM-owned references."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.activities import (
    Activity,
    ActivityId,
    ActivityParticipant,
    ActivityQuery,
    ActivityType,
)
from pycrmkit.contacts import (
    Contact,
    ContactEmail,
    ContactId,
    ContactPhone,
    ContactStatus,
)
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.custom_fields import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldType,
    CustomFieldValue,
    CustomFieldValueId,
)
from pycrmkit.dedup import (
    DedupDecision,
    DedupProvenance,
    DedupSignal,
    MergePolicy,
    MergeResolution,
    MergeService,
    SignalMatch,
)
from pycrmkit.exceptions import ConflictError, ValidationError
from pycrmkit.external_identities import (
    ExternalIdentity,
    ExternalIdentityId,
)
from pycrmkit.organizations import OrganizationId
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipId,
    RelationshipQuery,
    RelationshipType,
)
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork
from pycrmkit.tags import (
    Tag,
    TagAssignment,
    TagAssignmentId,
    TagId,
    TagName,
)


CREATED_AT = datetime(2026, 9, 27, 8, tzinfo=UTC)
MERGED_AT = datetime(2026, 9, 27, 9, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def _contact(
    suffix: int,
    *,
    emails: tuple[ContactEmail, ...] = (),
    phones: tuple[ContactPhone, ...] = (),
    metadata: dict[str, object] | None = None,
) -> Contact:
    return Contact(
        id=ContactId(_uuid(suffix)),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        first_name="Ada",
        last_name="Lovelace",
        emails=emails,
        phones=phones,
        metadata=metadata or {},
    )


def _provenance(
    duplicate_id: ContactId,
    *,
    decision: DedupDecision = DedupDecision.DUPLICATE,
) -> DedupProvenance:
    return DedupProvenance(
        candidate_entity_id=str(duplicate_id),
        score=100 if decision is DedupDecision.DUPLICATE else 70,
        decision=decision,
        matches=(
            SignalMatch(DedupSignal.EMAIL, "ada@example.com"),
        ),
    )


def test_merge_reassigns_owned_state_archives_duplicate_and_records_audit() -> None:
    store = MemoryStore()
    primary_id = ContactId(_uuid(101))
    duplicate_id = ContactId(_uuid(102))
    primary_ref = EntityReference("contact", primary_id)
    duplicate_ref = EntityReference("contact", duplicate_id)
    organization_id = OrganizationId(_uuid(201))
    organization_endpoint = RelationshipEndpoint.organization(organization_id)

    active_relationship_id = RelationshipId(_uuid(401))
    direct_relationship_id = RelationshipId(_uuid(402))
    activity_id = ActivityId(_uuid(301))
    vip_tag_id = TagId(_uuid(501))
    imported_tag_id = TagId(_uuid(502))
    definition_id = CustomFieldDefinitionId(_uuid(601))

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(
            _contact(
                101,
                emails=(ContactEmail("ada@example.com", is_primary=True),),
                metadata={"primary": True},
            )
        )
        uow.contacts.save(
            _contact(
                102,
                emails=(ContactEmail("ADA@EXAMPLE.COM", is_primary=True),),
                phones=(ContactPhone("+33612345678", is_primary=True),),
                metadata={"import_batch": "2026-09-27"},
            )
        )

        uow.activities.save(
            Activity(
                id=activity_id,
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                type=ActivityType.MEETING,
                occurred_at=CREATED_AT,
                subject="Duplicate review",
                participants=(
                    ActivityParticipant(primary_ref, role="owner"),
                    ActivityParticipant(
                        duplicate_ref,
                        role="guest",
                        is_primary=True,
                    ),
                ),
                references=(duplicate_ref, primary_ref),
            )
        )

        uow.relationships.save(
            Relationship(
                id=active_relationship_id,
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                source=RelationshipEndpoint.contact(duplicate_id),
                target=organization_endpoint,
                relationship_type=RelationshipType("works-at"),
                valid_from=CREATED_AT,
            )
        )
        uow.relationships.save(
            Relationship(
                id=direct_relationship_id,
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                source=RelationshipEndpoint.contact(primary_id),
                target=RelationshipEndpoint.contact(duplicate_id),
                relationship_type=RelationshipType("related-to"),
                valid_from=CREATED_AT,
            )
        )

        vip = Tag(
            id=vip_tag_id,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
            name=TagName("VIP"),
        )
        imported = Tag(
            id=imported_tag_id,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
            name=TagName("Imported"),
        )
        uow.tags.save(vip)
        uow.tags.save(imported)
        uow.tags.assign(
            TagAssignment(
                id=TagAssignmentId(_uuid(511)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                tag_id=vip_tag_id,
                entity=primary_ref,
            )
        )
        uow.tags.assign(
            TagAssignment(
                id=TagAssignmentId(_uuid(512)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                tag_id=vip_tag_id,
                entity=duplicate_ref,
            )
        )
        uow.tags.assign(
            TagAssignment(
                id=TagAssignmentId(_uuid(513)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                tag_id=imported_tag_id,
                entity=duplicate_ref,
            )
        )

        uow.custom_fields.save_definition(
            CustomFieldDefinition(
                id=definition_id,
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                key="segment",
                label="Segment",
                field_type=CustomFieldType.STRING,
                schema_version=1,
                applies_to=("contact",),
            )
        )
        uow.custom_fields.save_value(
            CustomFieldValue(
                id=CustomFieldValueId(_uuid(611)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                definition_id=definition_id,
                entity=duplicate_ref,
                schema_version=1,
                value="enterprise",
            )
        )

        uow.external_identities.save(
            ExternalIdentity(
                id=ExternalIdentityId(_uuid(701)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                system="hubspot",
                external_id="contact-42",
                entity_type="contact",
                entity_id=duplicate_id,
                metadata={"source": "sync"},
            )
        )
        uow.commit()

    service = MergeService(
        lambda: MemoryUnitOfWork(store),
        clock=FixedClock(MERGED_AT),
    )
    provenance = _provenance(duplicate_id)

    result = service.merge_contacts(
        primary_id=primary_id,
        duplicate_id=duplicate_id,
        provenance=provenance,
        actor_id="operator-1",
        correlation_id="merge-001",
    )

    assert result.primary.id == primary_id
    assert result.duplicate.status is ContactStatus.ARCHIVED
    assert result.provenance is provenance
    assert result.statistics.as_dict() == {
        "activities_reassigned": 1,
        "relationships_reassigned": 1,
        "relationships_ended": 1,
        "tags_added": 1,
        "custom_fields_moved": 1,
        "custom_field_conflicts": 0,
        "external_identities_moved": 1,
    }
    assert result.audit_entry.action == "contact.merged"
    assert result.audit_entry.correlation_id == "merge-001"

    with MemoryUnitOfWork(store) as uow:
        merged = uow.contacts.get(primary_id)
        archived = uow.contacts.get(duplicate_id)
        assert archived.status is ContactStatus.ARCHIVED
        assert merged.phones[0].normalized == "+33612345678"
        assert merged.metadata["import_batch"] == "2026-09-27"
        assert merged.metadata["primary"] is True

        activity = uow.activities.get(activity_id)
        assert activity.references == (primary_ref,)
        assert len(activity.participants) == 1
        assert activity.participants[0].reference == primary_ref
        assert activity.participants[0].is_primary is True
        assert activity.participants[0].role == "owner"
        assert uow.activities.list(
            ActivityQuery(participant=duplicate_ref),
            OffsetPageRequest(),
        ).total == 0

        active_relationship = uow.relationships.get(active_relationship_id)
        assert active_relationship.source == RelationshipEndpoint.contact(primary_id)
        assert active_relationship.target == organization_endpoint
        assert uow.relationships.get(direct_relationship_id).is_ended is True
        assert uow.relationships.search(
            RelationshipQuery(entity=RelationshipEndpoint.contact(duplicate_id)),
            OffsetPageRequest(),
        ).total == 0

        primary_tags = uow.tags.list_for_entity(primary_ref, OffsetPageRequest())
        duplicate_tags = uow.tags.list_for_entity(duplicate_ref, OffsetPageRequest())
        assert {tag.id for tag in primary_tags.items} == {vip_tag_id, imported_tag_id}
        assert duplicate_tags.total == 0

        value = uow.custom_fields.get_value(definition_id, primary_ref)
        assert value.value == "enterprise"
        assert uow.custom_fields.find_value(definition_id, duplicate_ref) is None

        identities = uow.external_identities.list_for_entity(
            primary_ref,
            OffsetPageRequest(),
        )
        assert identities.total == 1
        assert identities.items[0].external_id == "contact-42"
        assert uow.external_identities.list_for_entity(
            duplicate_ref,
            OffsetPageRequest(),
        ).total == 0

        audit = uow.audit.list_for_entity(
            "contact",
            str(primary_id),
            OffsetPageRequest(),
        )
        assert audit.total == 1
        assert audit.items[0].changes["duplicate_id"] == str(duplicate_id)
        assert audit.items[0].changes["provenance"]["score"] == 100
        assert audit.items[0].changes["provenance"]["matched_signals"] == ("email",)


def test_custom_field_conflict_rolls_back_every_prior_merge_mutation() -> None:
    store = MemoryStore()
    primary_id = ContactId(_uuid(111))
    duplicate_id = ContactId(_uuid(112))
    primary_ref = EntityReference("contact", primary_id)
    duplicate_ref = EntityReference("contact", duplicate_id)
    tag_id = TagId(_uuid(521))
    definition_id = CustomFieldDefinitionId(_uuid(621))

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(
            _contact(
                111,
                emails=(ContactEmail("ada@example.com", is_primary=True),),
            )
        )
        uow.contacts.save(
            _contact(
                112,
                emails=(ContactEmail("ADA@example.com", is_primary=True),),
                phones=(ContactPhone("+33699999999", is_primary=True),),
            )
        )
        uow.tags.save(
            Tag(
                id=tag_id,
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                name=TagName("Duplicate-only"),
            )
        )
        uow.tags.assign(
            TagAssignment(
                id=TagAssignmentId(_uuid(522)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                tag_id=tag_id,
                entity=duplicate_ref,
            )
        )
        uow.custom_fields.save_definition(
            CustomFieldDefinition(
                id=definition_id,
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                key="tier",
                label="Tier",
                field_type=CustomFieldType.STRING,
                schema_version=1,
                applies_to=("contact",),
            )
        )
        uow.custom_fields.save_value(
            CustomFieldValue(
                id=CustomFieldValueId(_uuid(623)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                definition_id=definition_id,
                entity=primary_ref,
                schema_version=1,
                value="gold",
            )
        )
        uow.custom_fields.save_value(
            CustomFieldValue(
                id=CustomFieldValueId(_uuid(624)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                definition_id=definition_id,
                entity=duplicate_ref,
                schema_version=1,
                value="silver",
            )
        )
        uow.commit()

    service = MergeService(
        lambda: MemoryUnitOfWork(store),
        clock=FixedClock(MERGED_AT),
    )

    with pytest.raises(ConflictError) as error:
        service.merge_contacts(
            primary_id=primary_id,
            duplicate_id=duplicate_id,
            provenance=_provenance(duplicate_id),
        )

    assert error.value.code == "merge.custom_field.conflict"

    with MemoryUnitOfWork(store) as uow:
        assert uow.contacts.get(duplicate_id).status is ContactStatus.ACTIVE
        assert uow.contacts.get(primary_id).phones == ()
        assert uow.tags.list_for_entity(primary_ref, OffsetPageRequest()).total == 0
        assert uow.tags.list_for_entity(duplicate_ref, OffsetPageRequest()).total == 1
        assert uow.custom_fields.get_value(definition_id, primary_ref).value == "gold"
        assert uow.custom_fields.get_value(definition_id, duplicate_ref).value == "silver"
        assert uow.audit.list_for_entity(
            "contact",
            str(primary_id),
            OffsetPageRequest(),
        ).total == 0


def test_custom_field_policy_can_keep_duplicate_value() -> None:
    store = MemoryStore()
    primary_id = ContactId(_uuid(121))
    duplicate_id = ContactId(_uuid(122))
    primary_ref = EntityReference("contact", primary_id)
    duplicate_ref = EntityReference("contact", duplicate_id)
    definition_id = CustomFieldDefinitionId(_uuid(631))

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(
            _contact(
                121,
                emails=(ContactEmail("ada@example.com", is_primary=True),),
            )
        )
        uow.contacts.save(
            _contact(
                122,
                emails=(ContactEmail("ADA@example.com", is_primary=True),),
            )
        )
        uow.custom_fields.save_definition(
            CustomFieldDefinition(
                id=definition_id,
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                key="tier",
                label="Tier",
                field_type=CustomFieldType.STRING,
                schema_version=1,
                applies_to=("contact",),
            )
        )
        uow.custom_fields.save_value(
            CustomFieldValue(
                id=CustomFieldValueId(_uuid(632)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                definition_id=definition_id,
                entity=primary_ref,
                schema_version=1,
                value="gold",
            )
        )
        uow.custom_fields.save_value(
            CustomFieldValue(
                id=CustomFieldValueId(_uuid(633)),
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
                definition_id=definition_id,
                entity=duplicate_ref,
                schema_version=1,
                value="platinum",
            )
        )
        uow.commit()

    result = MergeService(
        lambda: MemoryUnitOfWork(store),
        clock=FixedClock(MERGED_AT),
    ).merge_contacts(
        primary_id=primary_id,
        duplicate_id=duplicate_id,
        provenance=_provenance(duplicate_id),
        policy=MergePolicy(
            custom_field_conflict=MergeResolution.KEEP_DUPLICATE,
        ),
    )

    assert result.statistics.custom_field_conflicts == 1
    assert result.statistics.custom_fields_moved == 1
    with MemoryUnitOfWork(store) as uow:
        assert uow.custom_fields.get_value(definition_id, primary_ref).value == "platinum"
        assert uow.custom_fields.find_value(definition_id, duplicate_ref) is None


def test_merge_requires_matching_duplicate_provenance_by_default() -> None:
    store = MemoryStore()
    primary_id = ContactId(_uuid(131))
    duplicate_id = ContactId(_uuid(132))
    service = MergeService(
        lambda: MemoryUnitOfWork(store),
        clock=FixedClock(MERGED_AT),
    )

    with pytest.raises(ValidationError) as missing:
        service.merge_contacts(
            primary_id=primary_id,
            duplicate_id=duplicate_id,
        )
    assert missing.value.code == "merge.provenance.required"

    wrong_candidate = DedupProvenance(
        candidate_entity_id="different-candidate",
        score=100,
        decision=DedupDecision.DUPLICATE,
        matches=(),
    )
    with pytest.raises(ValidationError) as mismatch:
        service.merge_contacts(
            primary_id=primary_id,
            duplicate_id=duplicate_id,
            provenance=wrong_candidate,
        )
    assert mismatch.value.code == "merge.provenance.candidate_mismatch"

    with pytest.raises(ConflictError) as review:
        service.merge_contacts(
            primary_id=primary_id,
            duplicate_id=duplicate_id,
            provenance=_provenance(
                duplicate_id,
                decision=DedupDecision.REVIEW,
            ),
        )
    assert review.value.code == "merge.provenance.decision.invalid"
