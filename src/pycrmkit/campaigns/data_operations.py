"""Provider-neutral Campaign membership import and paginated exports.

Only direct members are inserted. Captured Segment snapshots are never altered.
HTTP integrations and persistence adapters are intentionally absent here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from itertools import islice
from typing import Literal, Protocol, TypeVar
from uuid import UUID

from pycrmkit.campaigns.audience import CampaignMember, CampaignSegmentSource
from pycrmkit.campaigns.entities import Campaign, CampaignId
from pycrmkit.contacts import ContactId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ValidationError
from pycrmkit.exporters import CSVExporter, JSONExporter, JSONLExporter
from pycrmkit.exporters.csv import TextDestination
from pycrmkit.importers import (
    DuplicateResult,
    IdentityMapper,
    ImportMapper,
    ImportReader,
    ImportReport,
    ImportRow,
    ImportStage,
    PersistAction,
    PersistResult,
    ValidationIssue,
)
from pycrmkit.leads import LeadId
from pycrmkit.opportunities import OpportunityId
from pycrmkit.organizations import OrganizationId

MAX_CAMPAIGN_IMPORT_ROWS = 1000
_ENTITY_ID_TYPES = {
    "contact": ContactId,
    "organization": OrganizationId,
    "lead": LeadId,
    "opportunity": OpportunityId,
}
ExportKind = Literal["direct", "audience", "sources"]
ExportFormat = Literal["csv", "json", "jsonl"]
_T = TypeVar("_T")


class CampaignDataOperationsAPI(Protocol):
    """Minimal public Campaign facade used by Data Operations."""

    def get(self, campaign_id: CampaignId) -> Campaign: ...

    def add_member(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
        *,
        source: str = "manual",
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignMember: ...

    def members(
        self, campaign_id: CampaignId, page: OffsetPageRequest | None = None
    ) -> Page[CampaignMember]: ...

    def audience(
        self, campaign_id: CampaignId, page: OffsetPageRequest | None = None
    ) -> Page[EntityReference]: ...

    def segment_sources(
        self, campaign_id: CampaignId, page: OffsetPageRequest | None = None
    ) -> Page[CampaignSegmentSource]: ...


def _canonical_reference(values: Mapping[str, object]) -> EntityReference:
    raw_kind = values["entity_kind"]
    raw_id = values["entity_id"]
    assert isinstance(raw_kind, str)
    assert isinstance(raw_id, str)
    kind = raw_kind.strip().casefold()
    return EntityReference(kind, _ENTITY_ID_TYPES[kind].parse(raw_id.strip()))


def _identity(reference: EntityReference) -> tuple[str, str]:
    return reference.kind, str(reference.id)


@dataclass(frozen=True, slots=True)
class CampaignMembershipValidator:
    """Validate flat input records without touching any CRM entity."""

    def validate(self, row: ImportRow) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        raw_kind = row.values.get("entity_kind")
        raw_id = row.values.get("entity_id")
        if not isinstance(raw_kind, str) or not raw_kind.strip():
            issues.append(ValidationIssue(
                "campaign.import.entity_kind.required",
                "entity_kind is required", "entity_kind"
            ))
        elif raw_kind.strip().casefold() not in _ENTITY_ID_TYPES:
            issues.append(ValidationIssue(
                "campaign.import.entity_kind.unsupported",
                "entity_kind is not supported", "entity_kind"
            ))
        if not isinstance(raw_id, str) or not raw_id.strip():
            issues.append(ValidationIssue(
                "campaign.import.entity_id.required",
                "entity_id is required", "entity_id"
            ))
        else:
            try:
                UUID(raw_id.strip())
            except ValueError:
                issues.append(ValidationIssue(
                    "campaign.import.entity_id.invalid",
                    "entity_id must be a valid UUID", "entity_id"
                ))
        return tuple(issues)


@dataclass(slots=True)
class CampaignMembershipDeduplicator:
    """Track only direct Campaign members, not captured Segment members."""

    existing: set[tuple[str, str]] = field(default_factory=set)

    def detect(self, row: ImportRow) -> DuplicateResult:
        ref = _canonical_reference(row.values)
        if _identity(ref) in self.existing:
            return DuplicateResult.match(
                existing_entity_id=str(ref.id),
                reason="direct membership already exists",
            )
        return DuplicateResult.no_match()

    def remember(self, reference: EntityReference) -> None:
        self.existing.add(_identity(reference))


@dataclass(slots=True)
class CampaignMembershipPersister:
    """Use one facade transaction per accepted direct membership."""

    campaigns: CampaignDataOperationsAPI
    campaign_id: CampaignId
    deduplicator: CampaignMembershipDeduplicator
    source: str = "import"

    def persist(self, row: ImportRow) -> PersistResult:
        reference = _canonical_reference(row.values)
        self.campaigns.add_member(
            self.campaign_id,
            reference,
            source=self.source,
            metadata={"import_row": row.number},
        )
        self.deduplicator.remember(reference)
        return PersistResult(
            action=PersistAction.CREATED,
            entity_id=str(reference.id),
        )


def _pages(
    get_page: Callable[[OffsetPageRequest], Page[_T]],
    *,
    page_size: int,
) -> Iterator[_T]:
    offset = 0
    while True:
        page = get_page(OffsetPageRequest(limit=page_size, offset=offset))
        yield from page.items
        if not page.has_next:
            return
        if not page.items:
            raise RuntimeError("Campaign page signalled more results without items")
        offset += len(page.items)


def import_campaign_members(
    campaigns: CampaignDataOperationsAPI,
    campaign_id: CampaignId,
    reader: ImportReader,
    *,
    source: str = "import",
    mapper: ImportMapper | None = None,
    max_rows: int = MAX_CAMPAIGN_IMPORT_ROWS,
    retain_row_results: bool = True,
) -> ImportReport:
    """Import a bounded file as direct Campaign members with per-row evidence.

    The input is pre-read up to max_rows+1 to reject oversized/invalid files
    before writing. Successful rows commit individually: no batch rollback is
    promised. Only known missing-entity domain errors are row-local. Any
    other persistence failure propagates; partial commits may already exist.
    """
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_CAMPAIGN_IMPORT_ROWS:
        raise ValidationError(
            "Campaign import max_rows must be between 1 and 1000",
            code="campaign.import.max_rows.invalid",
        )
    if not isinstance(source, str) or not source.strip() or len(source) > 120:
        raise ValidationError(
            "Campaign import source must be a nonempty bounded string",
            code="campaign.import.source.invalid",
        )
    campaigns.get(campaign_id).ensure_mutable()

    buffered = list(islice(reader.read(), max_rows + 1))
    if len(buffered) > max_rows:
        raise ValidationError(
            "Campaign import exceeds configured maximum rows",
            code="campaign.import.row_limit",
            context={"max_rows": max_rows},
        )

    # The facade's audience() is a union. Only members() yields direct rows.
    existing = {
        _identity(member.entity)
        for member in _pages(
            lambda page: campaigns.members(campaign_id, page),
            page_size=OffsetPageRequest.MAX_LIMIT,
        )
    }
    dedupe = CampaignMembershipDeduplicator(existing)
    persister = CampaignMembershipPersister(
        campaigns, campaign_id, dedupe, source.strip()
    )
    effective_mapper = mapper if mapper is not None else IdentityMapper()
    validator = CampaignMembershipValidator()
    report = ImportReport(retain_row_results=retain_row_results)
    for number, values in enumerate(buffered, start=1):
        report.rows_read += 1
        row = ImportRow(number, values)
        try:
            row = effective_mapper.map(row)
        except ValidationError as error:
            report.record_validation_failure(
                row_number=number,
                stage=ImportStage.MAP,
                issues=(ValidationIssue(error.code, error.message),),
            )
            continue
        issues = validator.validate(row)
        if issues:
            report.record_validation_failure(
                row_number=number, stage=ImportStage.VALIDATE, issues=issues
            )
            continue
        duplicate = dedupe.detect(row)
        if duplicate.is_duplicate:
            report.record_duplicate(
                row_number=number,
                existing_entity_id=duplicate.existing_entity_id,
            )
            continue
        try:
            result = persister.persist(row)
        except ValidationError as error:
            if error.code != "campaign.member.not_found":
                raise
            # The domain validates target existence inside its transaction.
            # This known missing-entity condition is a row-level validation
            # error, not a fabricated successful persistence outcome.
            report.record_validation_failure(
                row_number=number,
                stage=ImportStage.VALIDATE,
                issues=(ValidationIssue(
                    error.code, error.message, field="entity_id"
                ),),
            )
            continue
        report.record_persisted(row_number=number, result=result)
    return report

def iter_campaign_direct_member_records(
    campaigns: CampaignDataOperationsAPI,
    campaign_id: CampaignId,
    *,
    page_size: int = OffsetPageRequest.DEFAULT_LIMIT,
) -> Iterator[Mapping[str, object]]:
    """Export direct membership only, without actor identity."""
    OffsetPageRequest(limit=page_size)
    campaigns.get(campaign_id)
    for member in _pages(
        lambda page: campaigns.members(campaign_id, page), page_size=page_size
    ):
        yield {
            "campaign_id": str(campaign_id),
            "entity_kind": member.entity.kind,
            "entity_id": str(member.entity.id),
            "source": member.source,
            "added_at": member.added_at.isoformat(),
        }


def iter_campaign_audience_records(
    campaigns: CampaignDataOperationsAPI,
    campaign_id: CampaignId,
    *,
    page_size: int = OffsetPageRequest.DEFAULT_LIMIT,
) -> Iterator[Mapping[str, object]]:
    """Export deduplicated audience; no fabricated single provenance source."""
    OffsetPageRequest(limit=page_size)
    campaigns.get(campaign_id)
    for entity in _pages(
        lambda page: campaigns.audience(campaign_id, page), page_size=page_size
    ):
        yield {
            "campaign_id": str(campaign_id),
            "entity_kind": entity.kind,
            "entity_id": str(entity.id),
        }


def iter_campaign_segment_source_records(
    campaigns: CampaignDataOperationsAPI,
    campaign_id: CampaignId,
    *,
    page_size: int = OffsetPageRequest.DEFAULT_LIMIT,
) -> Iterator[Mapping[str, object]]:
    """Export captured Segment provenance without customer personal data."""
    OffsetPageRequest(limit=page_size)
    campaigns.get(campaign_id)
    for item in _pages(
        lambda page: campaigns.segment_sources(campaign_id, page),
        page_size=page_size,
    ):
        yield {
            "campaign_id": str(campaign_id),
            "segment_id": str(item.segment_id),
            "segment_revision": item.segment_revision,
            "entity_kind": item.entity_kind,
            "attached_at": item.attached_at.isoformat(),
            "captured_at": item.captured_at.isoformat(),
            "member_count": item.member_count,
        }


_FIELDS: dict[ExportKind, tuple[str, ...]] = {
    "direct": ("campaign_id", "entity_kind", "entity_id", "source", "added_at"),
    "audience": ("campaign_id", "entity_kind", "entity_id"),
    "sources": (
        "campaign_id", "segment_id", "segment_revision", "entity_kind",
        "attached_at", "captured_at", "member_count",
    ),
}


def export_campaign_records(
    campaigns: CampaignDataOperationsAPI,
    campaign_id: CampaignId,
    destination: TextDestination,
    *,
    kind: ExportKind,
    format: ExportFormat,
    page_size: int = OffsetPageRequest.DEFAULT_LIMIT,
) -> int:
    """Stream Campaign records through the existing CSV/JSON/JSONL exporters."""
    if kind not in _FIELDS:
        raise ValidationError(
            "unsupported Campaign export kind", code="campaign.export.kind.invalid"
        )
    if format not in ("csv", "json", "jsonl"):
        raise ValidationError(
            "unsupported Campaign export format",
            code="campaign.export.format.invalid",
        )
    OffsetPageRequest(limit=page_size)
    readers = {
        "direct": iter_campaign_direct_member_records,
        "audience": iter_campaign_audience_records,
        "sources": iter_campaign_segment_source_records,
    }
    records = readers[kind](campaigns, campaign_id, page_size=page_size)
    if format == "csv":
        return CSVExporter(destination, fieldnames=_FIELDS[kind]).write(records)
    if format == "json":
        return JSONExporter(destination).write(records)
    return JSONLExporter(destination).write(records)


__all__ = [
    "MAX_CAMPAIGN_IMPORT_ROWS",
    "CampaignDataOperationsAPI",
    "CampaignMembershipValidator",
    "CampaignMembershipDeduplicator",
    "CampaignMembershipPersister",
    "import_campaign_members",
    "iter_campaign_direct_member_records",
    "iter_campaign_audience_records",
    "iter_campaign_segment_source_records",
    "export_campaign_records",
]
