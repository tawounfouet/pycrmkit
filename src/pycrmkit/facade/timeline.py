"""Timeline facade namespace."""

from __future__ import annotations

from datetime import datetime

from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventType
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.organizations import OrganizationId
from pycrmkit.timeline import TimelineEntry, TimelineEntryId, TimelineEntryKind


class TimelineAPI:
    """Read-only customer relationship history namespace."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def get(self, entry_id: TimelineEntryId) -> TimelineEntry:
        with self._runtime.uow_factory() as uow:
            return uow.timeline.get(entry_id)

    def for_contact(
        self,
        contact_id: ContactId,
        page: OffsetPageRequest | None = None,
        *,
        kind: TimelineEntryKind | None = None,
        event_type: EventType | str | None = None,
        occurred_from: datetime | None = None,
        occurred_until: datetime | None = None,
    ) -> Page[TimelineEntry]:
        """Return reverse-chronological relationship history for one contact."""

        return self._for_reference(
            EntityReference(kind="contact", id=contact_id),
            page,
            kind=kind,
            event_type=event_type,
            occurred_from=occurred_from,
            occurred_until=occurred_until,
        )

    def for_organization(
        self,
        organization_id: OrganizationId,
        page: OffsetPageRequest | None = None,
        *,
        kind: TimelineEntryKind | None = None,
        event_type: EventType | str | None = None,
        occurred_from: datetime | None = None,
        occurred_until: datetime | None = None,
    ) -> Page[TimelineEntry]:
        """Return reverse-chronological relationship history for one organization."""

        return self._for_reference(
            EntityReference(kind="organization", id=organization_id),
            page,
            kind=kind,
            event_type=event_type,
            occurred_from=occurred_from,
            occurred_until=occurred_until,
        )

    def _for_reference(
        self,
        reference: EntityReference,
        page: OffsetPageRequest | None,
        *,
        kind: TimelineEntryKind | None,
        event_type: EventType | str | None,
        occurred_from: datetime | None,
        occurred_until: datetime | None,
    ) -> Page[TimelineEntry]:
        with self._runtime.uow_factory() as uow:
            return uow.timeline.list_for_reference(
                reference,
                page or OffsetPageRequest(),
                kind=kind,
                event_type=event_type,
                occurred_from=occurred_from,
                occurred_until=occurred_until,
            )
