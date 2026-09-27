"""Transactional contact merge orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TypeVar

from pycrmkit.activities import Activity, ActivityParticipant, ActivityQuery
from pycrmkit.audit import AuditService
from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.custom_fields import CustomFieldValue
from pycrmkit.dedup.merge import (
    MergePolicy,
    MergeResolution,
    MergeResult,
    MergeStatistics,
    merge_contact_profile,
)
from pycrmkit.dedup.provenance import DedupProvenance
from pycrmkit.dedup.scoring import DedupDecision
from pycrmkit.exceptions import ConflictError, ValidationError
from pycrmkit.external_identities import ExternalIdentity
from pycrmkit.relationships import Relationship, RelationshipEndpoint, RelationshipQuery
from pycrmkit.tags import Tag, TagAssignment, TagAssignmentId

T = TypeVar("T")


def _collect_pages(
    fetch: Callable[[OffsetPageRequest], Page[T]],
) -> tuple[T, ...]:
    items: list[T] = []
    offset = 0
    while True:
        page = fetch(
            OffsetPageRequest(
                limit=OffsetPageRequest.MAX_LIMIT,
                offset=offset,
            )
        )
        items.extend(page.items)
        if not page.has_next:
            return tuple(items)
        offset += len(page.items)


def _merge_activity(
    activity: Activity,
    *,
    duplicate: EntityReference,
    primary: EntityReference,
    updated_at: object,
) -> Activity:
    participants: list[ActivityParticipant] = []
    participant_index: dict[EntityReference, int] = {}

    for participant in activity.participants:
        reference = primary if participant.reference == duplicate else participant.reference
        current_index = participant_index.get(reference)
        if current_index is None:
            participant_index[reference] = len(participants)
            participants.append(replace(participant, reference=reference))
            continue

        current = participants[current_index]
        participants[current_index] = ActivityParticipant(
            reference=reference,
            role=current.role or participant.role,
            is_primary=current.is_primary or participant.is_primary,
        )

    references: list[EntityReference] = []
    for reference in activity.references:
        candidate = primary if reference == duplicate else reference
        if candidate not in references:
            references.append(candidate)

    return replace(
        activity,
        updated_at=updated_at,
        participants=tuple(participants),
        references=tuple(references),
    )


@dataclass(slots=True)
class MergeService:
    """Execute conservative Contact merges inside one Unit of Work."""

    uow_factory: Callable[[], UnitOfWork]
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)
    policy: MergePolicy = field(default_factory=MergePolicy)

    def merge_contacts(
        self,
        *,
        primary_id: ContactId,
        duplicate_id: ContactId,
        provenance: DedupProvenance | None = None,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        policy: MergePolicy | None = None,
    ) -> MergeResult:
        """Merge duplicate Contact state into an explicitly selected primary."""

        if primary_id == duplicate_id:
            raise ValidationError(
                "primary and duplicate contacts must be different records",
                code="merge.contact.same_record",
            )

        selected_policy = policy or self.policy
        self._validate_provenance(
            duplicate_id=duplicate_id,
            provenance=provenance,
            policy=selected_policy,
        )
        now = self.clock.now()

        with self.uow_factory() as uow:
            primary = uow.contacts.get(primary_id)
            duplicate = uow.contacts.get(duplicate_id)
            merged = merge_contact_profile(
                primary,
                duplicate,
                at=now,
                policy=selected_policy,
            )
            uow.contacts.save(merged)

            primary_ref = EntityReference("contact", primary_id)
            duplicate_ref = EntityReference("contact", duplicate_id)

            activities_reassigned = self._reassign_activities(
                uow,
                duplicate_ref=duplicate_ref,
                primary_ref=primary_ref,
                now=now,
            )
            relationships_reassigned, relationships_ended = self._reassign_relationships(
                uow,
                duplicate_id=duplicate_id,
                primary_id=primary_id,
                now=now,
            )
            tags_added = self._merge_tags(
                uow,
                duplicate_ref=duplicate_ref,
                primary_ref=primary_ref,
                now=now,
            )
            custom_fields_moved, custom_field_conflicts = self._merge_custom_fields(
                uow,
                duplicate_ref=duplicate_ref,
                primary_ref=primary_ref,
                now=now,
                resolution=selected_policy.custom_field_conflict,
            )
            external_identities_moved = self._move_external_identities(
                uow,
                duplicate_ref=duplicate_ref,
                primary_ref=primary_ref,
                now=now,
            )

            archived_duplicate = uow.contacts.archive(duplicate_id, now)
            statistics = MergeStatistics(
                activities_reassigned=activities_reassigned,
                relationships_reassigned=relationships_reassigned,
                relationships_ended=relationships_ended,
                tags_added=tags_added,
                custom_fields_moved=custom_fields_moved,
                custom_field_conflicts=custom_field_conflicts,
                external_identities_moved=external_identities_moved,
            )

            audit_entry = AuditService(
                uow.audit,
                id_factory=self.id_factory,
                clock=self.clock,
            ).record(
                action="contact.merged",
                entity_type="contact",
                entity_id=primary_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                changes=self._audit_changes(
                    duplicate_id=duplicate_id,
                    statistics=statistics,
                    provenance=provenance,
                    policy=selected_policy,
                ),
            )

            uow.commit()
            return MergeResult(
                primary=merged,
                duplicate=archived_duplicate,
                statistics=statistics,
                audit_entry=audit_entry,
                provenance=provenance,
            )

    @staticmethod
    def _validate_provenance(
        *,
        duplicate_id: ContactId,
        provenance: DedupProvenance | None,
        policy: MergePolicy,
    ) -> None:
        if provenance is not None and provenance.candidate_entity_id != str(duplicate_id):
            raise ValidationError(
                "merge provenance candidate does not match duplicate contact",
                code="merge.provenance.candidate_mismatch",
            )
        if not policy.require_duplicate_provenance:
            return
        if provenance is None:
            raise ValidationError(
                "merge requires duplicate provenance under the selected policy",
                code="merge.provenance.required",
            )
        if provenance.decision is not DedupDecision.DUPLICATE:
            raise ConflictError(
                "merge provenance must carry a duplicate decision",
                code="merge.provenance.decision.invalid",
                context={"decision": provenance.decision.value},
            )

    @staticmethod
    def _reassign_activities(
        uow: UnitOfWork,
        *,
        duplicate_ref: EntityReference,
        primary_ref: EntityReference,
        now: object,
    ) -> int:
        by_id: dict[object, Activity] = {}
        for activity in _collect_pages(
            lambda page: uow.activities.list(
                ActivityQuery(participant=duplicate_ref),
                page,
            )
        ):
            by_id[activity.id] = activity
        for activity in _collect_pages(
            lambda page: uow.activities.list(
                ActivityQuery(reference=duplicate_ref),
                page,
            )
        ):
            by_id[activity.id] = activity

        for activity in by_id.values():
            uow.activities.save(
                _merge_activity(
                    activity,
                    duplicate=duplicate_ref,
                    primary=primary_ref,
                    updated_at=now,
                )
            )
        return len(by_id)

    @staticmethod
    def _reassign_relationships(
        uow: UnitOfWork,
        *,
        duplicate_id: ContactId,
        primary_id: ContactId,
        now: object,
    ) -> tuple[int, int]:
        duplicate_endpoint = RelationshipEndpoint.contact(duplicate_id)
        primary_endpoint = RelationshipEndpoint.contact(primary_id)
        relationships = _collect_pages(
            lambda page: uow.relationships.search(
                RelationshipQuery(entity=duplicate_endpoint),
                page,
            )
        )
        reassigned = 0
        ended = 0
        for relationship in relationships:
            other_is_primary = (
                relationship.source == primary_endpoint
                or relationship.target == primary_endpoint
            )
            if other_is_primary:
                uow.relationships.end(relationship.id, now)
                ended += 1
                continue

            source = (
                primary_endpoint
                if relationship.source == duplicate_endpoint
                else relationship.source
            )
            target = (
                primary_endpoint
                if relationship.target == duplicate_endpoint
                else relationship.target
            )
            updated: Relationship = replace(
                relationship,
                updated_at=now,
                source=source,
                target=target,
            )
            uow.relationships.save(updated)
            reassigned += 1
        return reassigned, ended

    def _merge_tags(
        self,
        uow: UnitOfWork,
        *,
        duplicate_ref: EntityReference,
        primary_ref: EntityReference,
        now: object,
    ) -> int:
        primary_tags = {
            tag.id
            for tag in _collect_pages(
                lambda page: uow.tags.list_for_entity(primary_ref, page)
            )
        }
        duplicate_tags: tuple[Tag, ...] = _collect_pages(
            lambda page: uow.tags.list_for_entity(duplicate_ref, page)
        )

        added = 0
        for tag in duplicate_tags:
            if tag.id not in primary_tags:
                uow.tags.assign(
                    TagAssignment(
                        id=self.id_factory.new(TagAssignmentId),
                        created_at=now,
                        updated_at=now,
                        tag_id=tag.id,
                        entity=primary_ref,
                    )
                )
                primary_tags.add(tag.id)
                added += 1
            uow.tags.remove(tag.id, duplicate_ref, now)
        return added

    @staticmethod
    def _merge_custom_fields(
        uow: UnitOfWork,
        *,
        duplicate_ref: EntityReference,
        primary_ref: EntityReference,
        now: object,
        resolution: MergeResolution,
    ) -> tuple[int, int]:
        primary_values = {
            value.definition_id: value
            for value in _collect_pages(
                lambda page: uow.custom_fields.list_values(primary_ref, page)
            )
        }
        duplicate_values: tuple[CustomFieldValue, ...] = _collect_pages(
            lambda page: uow.custom_fields.list_values(duplicate_ref, page)
        )

        moved = 0
        conflicts = 0
        for duplicate_value in duplicate_values:
            primary_value = primary_values.get(duplicate_value.definition_id)
            if primary_value is None:
                uow.custom_fields.remove_value(
                    duplicate_value.definition_id,
                    duplicate_ref,
                )
                moved_value = replace(
                    duplicate_value,
                    updated_at=now,
                    entity=primary_ref,
                )
                uow.custom_fields.save_value(moved_value)
                primary_values[duplicate_value.definition_id] = moved_value
                moved += 1
                continue

            if primary_value.value == duplicate_value.value:
                uow.custom_fields.remove_value(
                    duplicate_value.definition_id,
                    duplicate_ref,
                )
                continue

            conflicts += 1
            if resolution is MergeResolution.REJECT:
                raise ConflictError(
                    "custom field values conflict during contact merge",
                    code="merge.custom_field.conflict",
                    context={
                        "definition_id": str(duplicate_value.definition_id),
                    },
                )
            if resolution is MergeResolution.KEEP_PRIMARY:
                uow.custom_fields.remove_value(
                    duplicate_value.definition_id,
                    duplicate_ref,
                )
                continue

            uow.custom_fields.remove_value(
                duplicate_value.definition_id,
                primary_ref,
            )
            uow.custom_fields.remove_value(
                duplicate_value.definition_id,
                duplicate_ref,
            )
            moved_value = replace(
                duplicate_value,
                updated_at=now,
                entity=primary_ref,
            )
            uow.custom_fields.save_value(moved_value)
            primary_values[duplicate_value.definition_id] = moved_value
            moved += 1

        return moved, conflicts

    @staticmethod
    def _move_external_identities(
        uow: UnitOfWork,
        *,
        duplicate_ref: EntityReference,
        primary_ref: EntityReference,
        now: object,
    ) -> int:
        identities: tuple[ExternalIdentity, ...] = _collect_pages(
            lambda page: uow.external_identities.list_for_entity(
                duplicate_ref,
                page,
            )
        )
        for identity in identities:
            uow.external_identities.remove(identity.system, identity.external_id)
            uow.external_identities.save(
                replace(
                    identity,
                    updated_at=now,
                    entity_type=primary_ref.kind,
                    entity_id=primary_ref.id,
                )
            )
        return len(identities)

    @staticmethod
    def _audit_changes(
        *,
        duplicate_id: ContactId,
        statistics: MergeStatistics,
        provenance: DedupProvenance | None,
        policy: MergePolicy,
    ) -> dict[str, object]:
        changes: dict[str, object] = {
            "duplicate_id": str(duplicate_id),
            "statistics": statistics.as_dict(),
            "policy": {
                "primary_email_conflict": policy.primary_email_conflict.value,
                "primary_phone_conflict": policy.primary_phone_conflict.value,
                "custom_field_conflict": policy.custom_field_conflict.value,
            },
        }
        if provenance is not None:
            changes["provenance"] = {
                "candidate_entity_id": provenance.candidate_entity_id,
                "score": provenance.score,
                "decision": provenance.decision.value,
                "matched_signals": sorted(
                    {match.signal.value for match in provenance.matches}
                ),
                "conflicts": [
                    {
                        "signal": conflict.signal.value,
                        "severity": conflict.severity.value,
                        "key": conflict.key,
                    }
                    for conflict in provenance.conflicts
                ],
            }
        return changes


__all__ = ["MergeService"]
