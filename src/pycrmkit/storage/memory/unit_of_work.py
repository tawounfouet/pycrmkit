"""Transactional in-memory Unit of Work implementation."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from pycrmkit.exceptions import InvalidStateError
from pycrmkit.storage.memory._state import MemoryStore, _MemoryState
from pycrmkit.storage.memory.contacts import MemoryContactRepository
from pycrmkit.storage.memory.custom_fields import MemoryCustomFieldRepository
from pycrmkit.storage.memory.organizations import MemoryOrganizationRepository
from pycrmkit.storage.memory.relationships import MemoryRelationshipRepository
from pycrmkit.storage.memory.tags import MemoryTagRepository


class MemoryUnitOfWork:
    """Explicit-commit transaction over one shared MemoryStore snapshot."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()
        self._active = False
        self._committed = False
        self._working: _MemoryState | None = None
        self._contacts: MemoryContactRepository | None = None
        self._organizations: MemoryOrganizationRepository | None = None
        self._relationships: MemoryRelationshipRepository | None = None
        self._tags: MemoryTagRepository | None = None
        self._custom_fields: MemoryCustomFieldRepository | None = None

    @property
    def contacts(self) -> MemoryContactRepository:
        self._ensure_active()
        assert self._contacts is not None
        return self._contacts

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
    def tags(self) -> MemoryTagRepository:
        self._ensure_active()
        assert self._tags is not None
        return self._tags

    @property
    def custom_fields(self) -> MemoryCustomFieldRepository:
        self._ensure_active()
        assert self._custom_fields is not None
        return self._custom_fields

    def __enter__(self) -> Self:
        if self._active:
            raise InvalidStateError(
                "MemoryUnitOfWork is already active",
                code="memory.uow.already_active",
            )
        self._working = self.store._begin()
        self._active = True
        self._committed = False
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
        self._active = False
        self.store._end()
        return None

    def commit(self) -> None:
        self._ensure_active()
        assert self._working is not None
        self.store._commit(self._working)
        self._committed = True

    def rollback(self) -> None:
        self._ensure_active()
        self._discard_working_state()
        self._committed = False

    def _discard_working_state(self) -> None:
        self._working = self.store._snapshot()
        self._bind_repositories(self._working)

    def _bind_repositories(self, state: _MemoryState) -> None:
        self._contacts = MemoryContactRepository(state)
        self._organizations = MemoryOrganizationRepository(state)
        self._relationships = MemoryRelationshipRepository(state)
        self._tags = MemoryTagRepository(state)
        self._custom_fields = MemoryCustomFieldRepository(state)

    def _ensure_active(self) -> None:
        if not self._active:
            raise InvalidStateError(
                "MemoryUnitOfWork must be entered before use",
                code="memory.uow.not_active",
            )
