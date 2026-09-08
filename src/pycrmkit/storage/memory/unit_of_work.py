"""Transactional in-memory Unit of Work implementation."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from pycrmkit.events.bus import InProcessEventBus
from pycrmkit.events.envelope import DomainEvent
from pycrmkit.events.publisher import EventPublisher
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.storage.memory._state import MemoryStore, _MemoryState
from pycrmkit.storage.memory.activities import MemoryActivityRepository
from pycrmkit.storage.memory.audit import MemoryAuditRepository
from pycrmkit.storage.memory.contacts import MemoryContactRepository
from pycrmkit.storage.memory.custom_fields import MemoryCustomFieldRepository
from pycrmkit.storage.memory.leads import MemoryLeadRepository
from pycrmkit.storage.memory.organizations import MemoryOrganizationRepository
from pycrmkit.storage.memory.relationships import MemoryRelationshipRepository
from pycrmkit.storage.memory.tags import MemoryTagRepository
from pycrmkit.storage.memory.tasks import MemoryTaskRepository
from pycrmkit.storage.memory.timeline import MemoryTimelineRepository


class MemoryUnitOfWork:
    """Explicit-commit transaction over one shared MemoryStore snapshot.

    Domain events are staged while the transaction is active and become eligible
    for synchronous in-process dispatch only after committed state has been
    published to the MemoryStore. Durable retry/outbox semantics are not provided.
    """

    def __init__(
        self,
        store: MemoryStore | None = None,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self.store = store or MemoryStore()
        self.event_publisher = event_publisher or InProcessEventBus()
        self._active = False
        self._committed = False
        self._working: _MemoryState | None = None
        self._activities: MemoryActivityRepository | None = None
        self._contacts: MemoryContactRepository | None = None
        self._leads: MemoryLeadRepository | None = None
        self._organizations: MemoryOrganizationRepository | None = None
        self._relationships: MemoryRelationshipRepository | None = None
        self._tasks: MemoryTaskRepository | None = None
        self._timeline: MemoryTimelineRepository | None = None
        self._tags: MemoryTagRepository | None = None
        self._custom_fields: MemoryCustomFieldRepository | None = None
        self._audit: MemoryAuditRepository | None = None
        self._pending_events: list[DomainEvent] = []

    @property
    def activities(self) -> MemoryActivityRepository:
        self._ensure_active()
        assert self._activities is not None
        return self._activities

    @property
    def contacts(self) -> MemoryContactRepository:
        self._ensure_active()
        assert self._contacts is not None
        return self._contacts

    @property
    def leads(self) -> MemoryLeadRepository:
        self._ensure_active()
        assert self._leads is not None
        return self._leads

    @property
    def organizations(self) -> MemoryOrganizationRepository:
        self._ensure_active()
        assert self._organizations is not None
        return self._organizations

    @property
    def relationships(self) -> MemoryRelationshipRepository:
        self._ensure_active()
        assert self._relationships is not None
        return self._relationships

    @property
    def tasks(self) -> MemoryTaskRepository:
        self._ensure_active()
        assert self._tasks is not None
        return self._tasks

    @property
    def timeline(self) -> MemoryTimelineRepository:
        self._ensure_active()
        assert self._timeline is not None
        return self._timeline

    @property
    def tags(self) -> MemoryTagRepository:
        self._ensure_active()
        assert self._tags is not None
        return self._tags

    @property
    def custom_fields(self) -> MemoryCustomFieldRepository:
        self._ensure_active()
        assert self._custom_fields is not None
        return self._custom_fields

    @property
    def audit(self) -> MemoryAuditRepository:
        self._ensure_active()
        assert self._audit is not None
        return self._audit

    def add_event(self, event: DomainEvent) -> None:
        """Stage one immutable event for dispatch after the next successful commit."""

        self._ensure_active()
        self._pending_events.append(event)

    @property
    def pending_events(self) -> tuple[DomainEvent, ...]:
        """Expose an immutable snapshot for diagnostics/tests while active."""

        self._ensure_active()
        return tuple(self._pending_events)

    def __enter__(self) -> Self:
        if self._active:
            raise InvalidStateError(
                "MemoryUnitOfWork is already active",
                code="memory.uow.already_active",
            )
        self._working = self.store._begin()
        self._active = True
        self._committed = False
        self._pending_events.clear()
        self._bind_repositories(self._working)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        del exc, traceback
        if not self._active:
            return None
        if exc_type is not None or not self._committed:
            self._discard_working_state()
        self._pending_events.clear()
        self._active = False
        self.store._end()
        return None

    def commit(self) -> None:
        self._ensure_active()
        assert self._working is not None
        events = tuple(self._pending_events)
        self.store._commit(self._working)
        self._committed = True
        self._pending_events.clear()
        for event in events:
            self.event_publisher.publish(event)

    def rollback(self) -> None:
        self._ensure_active()
        self._discard_working_state()
        self._pending_events.clear()
        self._committed = False

    def _discard_working_state(self) -> None:
        self._working = self.store._snapshot()
        self._bind_repositories(self._working)

    def _bind_repositories(self, state: _MemoryState) -> None:
        self._activities = MemoryActivityRepository(state)
        self._contacts = MemoryContactRepository(state)
        self._leads = MemoryLeadRepository(state)
        self._organizations = MemoryOrganizationRepository(state)
        self._relationships = MemoryRelationshipRepository(state)
        self._tasks = MemoryTaskRepository(state)
        self._timeline = MemoryTimelineRepository(state)
        self._tags = MemoryTagRepository(state)
        self._custom_fields = MemoryCustomFieldRepository(state)
        self._audit = MemoryAuditRepository(state)

    def _ensure_active(self) -> None:
        if not self._active:
            raise InvalidStateError(
                "MemoryUnitOfWork must be entered before use",
                code="memory.uow.not_active",
            )
