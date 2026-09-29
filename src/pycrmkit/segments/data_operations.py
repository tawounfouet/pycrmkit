"""Data Operations bridges for Segment membership.

The helpers in this module adapt the provider-neutral import/export contracts
without introducing file-format or persistence dependencies into the Segment
domain.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pycrmkit.contacts import ContactId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ValidationError
from pycrmkit.importers import (
    ImportPipeline,
    ImportReader,
    ImportReport,
    ImportRow,
    ImportValidator,
    PersistAction,
    PersistResult,
    ValidationIssue,
)
from pycrmkit.leads import LeadId
from pycrmkit.opportunities import OpportunityId
from pycrmkit.organizations import OrganizationId
from pycrmkit.segments.entities import Segment, SegmentId, SegmentMember

_ENTITY_ID_TYPES = {
    "contact": ContactId,
    "organization": OrganizationId,
    "lead": LeadId,
    "opportunity": OpportunityId,
}


class SegmentDataOperationsAPI(Protocol):
    """Minimal facade surface required by Segment data-operation adapters."""

    def get(self, segment_id: SegmentId) -> Segment:
        """Return one Segment."""

    def add_member(
        self,
        segment_id: SegmentId,
        entity: EntityReference,
        *,
        source: str = "manual",
        metadata: Mapping[str, object] | None = None,
    ) -> SegmentMember:
        """Persist one explicit membership."""

    def evaluate(
        self,
        segment_id: SegmentId,
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        """Evaluate or list one Segment population."""


@dataclass(frozen=True, slots=True)
class SegmentMembershipValidator(ImportValidator):
    """Validate the canonical membership import record."""

    entity_kind: str

    def validate(self, row: ImportRow) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        raw_kind = row.values.get("entity_kind", self.entity_kind)
        raw_id = row.values.get("entity_id")

        if not isinstance(raw_kind, str) or not raw_kind.strip():
            issues.append(
                ValidationIssue(
                    code="segment.import.entity_kind.required",
                    message="entity_kind is required",
                    field="entity_kind",
                )
            )
        elif raw_kind.strip().casefold() != self.entity_kind:
            issues.append(
                ValidationIssue(
                    code="segment.import.entity_kind.mismatch",
                    message="entity_kind must match the target Segment",
                    field="entity_kind",
                )
            )

        if not isinstance(raw_id, str) or not raw_id.strip():
            issues.append(
                ValidationIssue(
                    code="segment.import.entity_id.required",
                    message="entity_id is required",
                    field="entity_id",
                )
            )
        else:
            try:
                UUID(raw_id.strip())
            except ValueError:
                issues.append(
                    ValidationIssue(
                        code="segment.import.entity_id.invalid",
                        message="entity_id must be a valid UUID",
                        field="entity_id",
                    )
                )

        return tuple(issues)


@dataclass(slots=True)
class SegmentMembershipPersister:
    """Persist one canonical import row through the public Segment facade."""

    segments: SegmentDataOperationsAPI
    segment_id: SegmentId
    entity_kind: str
    source: str = "import"

    def persist(self, row: ImportRow) -> PersistResult:
        raw_id = row.values.get("entity_id")
        if not isinstance(raw_id, str):
            raise ValidationError(
                "validated membership row is missing entity_id",
                code="segment.import.entity_id.required",
                context={"field": "entity_id"},
            )
        reference = _reference(self.entity_kind, raw_id)
        self.segments.add_member(
            self.segment_id,
            reference,
            source=self.source,
            metadata={"import_row": row.number},
        )
        return PersistResult(
            PersistAction.CREATED,
            entity_id=str(reference.id),
        )


def import_segment_members(
    segments: SegmentDataOperationsAPI,
    segment_id: SegmentId,
    reader: ImportReader,
    *,
    source: str = "import",
    retain_row_results: bool = True,
) -> ImportReport:
    """Run a provider-neutral membership import into a Static Segment."""

    segment = segments.get(segment_id)
    pipeline = ImportPipeline(
        reader=reader,
        validator=SegmentMembershipValidator(segment.entity_kind),
        persister=SegmentMembershipPersister(
            segments=segments,
            segment_id=segment.id,
            entity_kind=segment.entity_kind,
            source=source,
        ),
        retain_row_results=retain_row_results,
    )
    return pipeline.run()


def iter_segment_membership_records(
    segments: SegmentDataOperationsAPI,
    segment_id: SegmentId,
    *,
    page_size: int = OffsetPageRequest.DEFAULT_LIMIT,
) -> Iterable[Mapping[str, object]]:
    """Yield portable export records for the current Segment population.

    Dynamic Segment exports are live by definition. Applications that need a
    reproducible export should create a Snapshot first.
    """

    segment = segments.get(segment_id)
    if page_size < 1 or page_size > OffsetPageRequest.MAX_LIMIT:
        raise ValidationError(
            "segment export page_size is outside pagination bounds",
            code="segment.export.page_size.invalid",
            context={"page_size": page_size},
        )

    offset = 0
    while True:
        page = segments.evaluate(
            segment.id,
            OffsetPageRequest(limit=page_size, offset=offset),
        )
        for entity in page.items:
            yield {
                "segment_id": str(segment.id),
                "segment_key": segment.key,
                "segment_mode": segment.mode.value,
                "entity_kind": entity.kind,
                "entity_id": str(entity.id),
            }
        if not page.has_next:
            return
        offset += len(page.items)


def _reference(entity_kind: str, raw_id: str) -> EntityReference:
    try:
        id_type = _ENTITY_ID_TYPES[entity_kind]
    except KeyError as exc:
        raise ValidationError(
            "unsupported segment entity kind",
            code="segment.entity_kind.unsupported",
            context={"entity_kind": entity_kind},
        ) from exc
    return EntityReference(entity_kind, id_type.parse(raw_id.strip()))


__all__ = [
    "SegmentDataOperationsAPI",
    "SegmentMembershipPersister",
    "SegmentMembershipValidator",
    "import_segment_members",
    "iter_segment_membership_records",
]
