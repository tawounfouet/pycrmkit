"""PyCRMKit 1.0.0b2 reference Data Operations E2E scenario."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from typing import cast

import pycrmkit
from pycrmkit.contacts import (
    Contact,
    ContactEmail,
    ContactId,
    ContactPhone,
    ContactQuery,
    ContactService,
    ContactStatus,
    normalize_email,
    normalize_phone,
)
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.dedup import (
    CandidateRecord,
    CandidateSource,
    DedupDecision,
    DeduplicationEngine,
    MergeService,
)
from pycrmkit.exporters import CSVExporter, JSONExporter, JSONLExporter
from pycrmkit.external_identities import ExternalIdentity, ExternalIdentityId
from pycrmkit.importers import (
    CSVReader,
    FieldMapping,
    ImportPipeline,
    ImportRow,
    JSONLReader,
    JSONReader,
    NormalizationRule,
    PersistAction,
    PersistResult,
    RecordMapper,
    RecordNormalizer,
    RequiredFieldsValidator,
    casefold_text,
    compose_normalizers,
    strip_text,
)
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)
CLOCK = FixedClock(NOW)

SOURCE_CSV = """First Name,Last Name,Email,Phone,Source
 Ada , Lovelace , ADA@Example.COM , +33 (6) 12 34 56 78 , Campaign Import
Ada,Lovelace,ada@example.com,+33612345678,Legacy CRM
Grace,Hopper,GRACE@EXAMPLE.COM,+1 202 555 0101,Campaign Import
Invalid,Missing,,+33611111111,Campaign Import
"""


def _required_text(values: Mapping[str, object], field: str) -> str:
    value = values.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a normalized non-empty string")
    return value


@dataclass(slots=True)
class MemoryContactImportPersister:
    store: MemoryStore
    clock: FixedClock

    def persist(self, row: ImportRow) -> PersistResult:
        with MemoryUnitOfWork(self.store) as uow:
            contact = ContactService(uow.contacts, clock=self.clock).create(
                first_name=_required_text(row.values, "first_name"),
                last_name=_required_text(row.values, "last_name"),
                source=_required_text(row.values, "source"),
                emails=(
                    ContactEmail(
                        _required_text(row.values, "email"),
                        is_primary=True,
                    ),
                ),
                phones=(
                    ContactPhone(
                        _required_text(row.values, "phone"),
                        is_primary=True,
                    ),
                ),
            )
            uow.commit()
        return PersistResult(PersistAction.CREATED, str(contact.id))


def _candidate_values(contact: Contact) -> dict[str, object]:
    return {
        "full_name": contact.display_name,
        "email": contact.emails[0].normalized if contact.emails else None,
        "phone": contact.phones[0].normalized if contact.phones else None,
    }


@dataclass(slots=True)
class StoreContactCandidateSource(CandidateSource):
    store: MemoryStore

    def candidates(self, row: ImportRow) -> Iterable[CandidateRecord]:
        excluded_id = row.values.get("entity_id")
        with MemoryUnitOfWork(self.store) as uow:
            contacts = uow.contacts.search(
                ContactQuery(),
                OffsetPageRequest(limit=OffsetPageRequest.MAX_LIMIT),
            ).items
        return tuple(
            CandidateRecord(str(contact.id), _candidate_values(contact))
            for contact in contacts
            if str(contact.id) != excluded_id
        )


def _contact_row(contact: Contact) -> ImportRow:
    values = _candidate_values(contact)
    values["entity_id"] = str(contact.id)
    return ImportRow(1, values)


def _created_id(report_row: object) -> ContactId:
    entity_id = getattr(report_row, "entity_id", None)
    if not isinstance(entity_id, str):
        raise AssertionError("expected a created Contact entity ID")
    return ContactId.parse(entity_id)


def _active_export_records(store: MemoryStore) -> tuple[dict[str, object], ...]:
    with MemoryUnitOfWork(store) as uow:
        contacts = uow.contacts.search(
            ContactQuery(),
            OffsetPageRequest(limit=OffsetPageRequest.MAX_LIMIT),
        ).items
    records = [
        {
            "entity_id": str(contact.id),
            "display_name": contact.display_name or "",
            "email": contact.emails[0].normalized if contact.emails else "",
            "phone": contact.phones[0].normalized if contact.phones else "",
            "source": contact.source or "",
        }
        for contact in contacts
    ]
    records.sort(key=lambda item: cast(str, item["display_name"]))
    return tuple(records)


def run_scenario() -> dict[str, object]:
    store = MemoryStore()
    report = ImportPipeline(
        reader=CSVReader(StringIO(SOURCE_CSV)),
        mapper=RecordMapper(
            (
                FieldMapping("First Name", "first_name"),
                FieldMapping("Last Name", "last_name"),
                FieldMapping("Email", "email"),
                FieldMapping("Phone", "phone"),
                FieldMapping("Source", "source"),
            )
        ),
        normalizer=RecordNormalizer(
            (
                NormalizationRule("first_name", strip_text),
                NormalizationRule("last_name", strip_text),
                NormalizationRule(
                    "email",
                    compose_normalizers(strip_text, normalize_email),
                ),
                NormalizationRule(
                    "phone",
                    compose_normalizers(strip_text, normalize_phone),
                ),
                NormalizationRule(
                    "source",
                    compose_normalizers(strip_text, casefold_text),
                ),
            )
        ),
        validator=RequiredFieldsValidator(
            ("first_name", "last_name", "email", "phone", "source")
        ),
        persister=MemoryContactImportPersister(store, CLOCK),
    ).run()

    assert report.as_dict() == {
        "rows_read": 4,
        "rows_created": 3,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 0,
        "validation_errors": 1,
    }

    primary_id = _created_id(report.row_results[0])
    duplicate_id = _created_id(report.row_results[1])

    with MemoryUnitOfWork(store) as uow:
        primary = uow.contacts.get(primary_id)
        uow.external_identities.save(
            ExternalIdentity(
                id=UUID4Factory().new(ExternalIdentityId),
                created_at=NOW,
                updated_at=NOW,
                system="legacy_crm",
                external_id="legacy-ada-42",
                entity_type="contact",
                entity_id=duplicate_id,
                metadata={"source": "1.0.0b2-e2e"},
            )
        )
        uow.commit()

    engine = DeduplicationEngine(StoreContactCandidateSource(store))
    review = next(
        item
        for item in engine.evaluate(_contact_row(primary))
        if item.candidate.entity_id == str(duplicate_id)
    )
    assert review.decision is DedupDecision.DUPLICATE
    assert review.score == 100

    merged = MergeService(
        lambda: MemoryUnitOfWork(store),
        clock=CLOCK,
    ).merge_contacts(
        primary_id=primary_id,
        duplicate_id=duplicate_id,
        provenance=review.provenance,
        actor_id="data-operations-e2e",
        correlation_id="1.0.0b2",
    )
    assert merged.duplicate.status is ContactStatus.ARCHIVED

    primary_ref = EntityReference("contact", primary_id)
    duplicate_ref = EntityReference("contact", duplicate_id)
    with MemoryUnitOfWork(store) as uow:
        identity = uow.external_identities.find("legacy_crm", "legacy-ada-42")
        audit = uow.audit.list_for_entity(
            "contact",
            str(primary_id),
            OffsetPageRequest(),
        )
        assert identity is not None
        assert identity.entity == primary_ref
        assert uow.external_identities.list_for_entity(
            duplicate_ref,
            OffsetPageRequest(),
        ).total == 0
        assert audit.total == 1
        assert audit.items[0].action == "contact.merged"
        provenance = audit.items[0].changes["provenance"]
        assert isinstance(provenance, Mapping)
        assert provenance["decision"] == "duplicate"

    records = _active_export_records(store)
    csv_output = StringIO()
    json_output = StringIO()
    jsonl_output = StringIO()
    assert CSVExporter(csv_output).write(records) == 2
    assert JSONExporter(json_output).write(records) == 2
    assert JSONLExporter(jsonl_output).write(records) == 2

    csv_records = tuple(CSVReader(StringIO(csv_output.getvalue())).read())
    json_records = tuple(JSONReader(StringIO(json_output.getvalue())).read())
    jsonl_records = tuple(JSONLReader(StringIO(jsonl_output.getvalue())).read())
    expected = tuple(dict(record) for record in records)
    assert csv_records == expected
    assert json_records == expected
    assert jsonl_records == expected

    return {
        "version": pycrmkit.__version__,
        "import": report.as_dict(),
        "review": {
            "decision": review.decision.value,
            "score": review.score,
            "matched_signals": sorted(
                {match.signal.value for match in review.provenance.matches}
            ),
        },
        "merge": {
            "audit_action": merged.audit_entry.action,
            "duplicate_archived": True,
            "external_identity_owner": "primary",
            "statistics": merged.statistics.as_dict(),
        },
        "export": {
            "active_contacts": len(records),
            "csv_rows": len(csv_records),
            "json_rows": len(json_records),
            "jsonl_rows": len(jsonl_records),
            "display_names": [
                cast(str, record["display_name"]) for record in records
            ],
        },
    }


def main() -> None:
    summary = run_scenario()
    assert summary["version"] == "1.0.0b2"
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
