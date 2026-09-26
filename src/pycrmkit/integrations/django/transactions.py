"""Django transaction bridge for the optional CRM persistence adapter."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from django.db import DatabaseError, transaction

from pycrmkit.events.bus import InProcessEventBus
from pycrmkit.events.envelope import DomainEvent
from pycrmkit.events.publisher import EventPublisher
from pycrmkit.exceptions import InvalidStateError, RepositoryError
from pycrmkit.integrations.django.repositories import (
    DjangoContactRepository,
    DjangoExternalIdentityRepository,
    DjangoOrganizationRepository,
    DjangoRelationshipRepository,
)


class _RollbackSignal(Exception):
    """Internal marker used to force rollback when leaving an atomic block."""


class DjangoTransactionBridge:
    """Explicit-commit transaction boundary for Django-backed CRM repositories.

    The bridge covers the Django repositories currently implemented by the
    0.8.x line. It uses Django atomic blocks internally and safely joins an
    ambient Django transaction through savepoints. Domain events are registered
    with on_commit so they are never published before the outermost database
    transaction succeeds.
    """

    def __init__(self, *, event_publisher: EventPublisher | None = None) -> None:
        self.event_publisher = event_publisher or InProcessEventBus()
        self._active = False
        self._committed = False
        self._transaction_open = False
        self._joined_ambient_transaction = False
        self._atomic: transaction.Atomic | None = None
        self._pending_events: list[DomainEvent] = []
        self._contacts: DjangoContactRepository | None = None
        self._external_identities: DjangoExternalIdentityRepository | None = None
        self._organizations: DjangoOrganizationRepository | None = None
        self._relationships: DjangoRelationshipRepository | None = None

    @property
    def contacts(self) -> DjangoContactRepository:
        self._ensure_writable()
        assert self._contacts is not None
        return self._contacts

    @property
    def external_identities(self) -> DjangoExternalIdentityRepository:
        self._ensure_writable()
        assert self._external_identities is not None
        return self._external_identities

    @property
    def organizations(self) -> DjangoOrganizationRepository:
        self._ensure_writable()
        assert self._organizations is not None
        return self._organizations

    @property
    def relationships(self) -> DjangoRelationshipRepository:
        self._ensure_writable()
        assert self._relationships is not None
        return self._relationships

    @property
    def pending_events(self) -> tuple[DomainEvent, ...]:
        self._ensure_writable()
        return tuple(self._pending_events)

    def add_event(self, event: DomainEvent) -> None:
        """Stage one event for publication after the outer transaction commits."""

        self._ensure_writable()
        self._pending_events.append(event)

    def __enter__(self) -> Self:
        if self._active:
            raise InvalidStateError(
                "DjangoTransactionBridge is already active",
                code="django.transaction.already_active",
            )

        self._active = True
        self._committed = False
        self._pending_events.clear()
        self._bind_repositories()
        try:
            self._open_atomic()
        except BaseException:
            self._active = False
            self._unbind_repositories()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if not self._active:
            return None

        try:
            if self._transaction_open:
                if exc_type is None:
                    self._rollback_current_atomic()
                else:
                    atomic = self._require_atomic()
                    atomic.__exit__(exc_type, exc, traceback)
                    self._transaction_open = False
                    self._atomic = None
        finally:
            self._pending_events.clear()
            self._transaction_open = False
            self._atomic = None
            self._active = False
            self._unbind_repositories()
        return None

    def commit(self) -> None:
        """Commit this bridge's block and defer events to the outer commit."""

        self._ensure_writable()
        events = tuple(self._pending_events)

        def publish_events() -> None:
            for event in events:
                self.event_publisher.publish(event)

        joined_ambient = self._joined_ambient_transaction
        if joined_ambient:
            transaction.on_commit(publish_events)

        atomic = self._require_atomic()
        try:
            atomic.__exit__(None, None, None)
        except DatabaseError as error:
            self._pending_events.clear()
            self._transaction_open = False
            self._atomic = None
            raise RepositoryError(
                "The Django transaction could not be committed",
                code="django.transaction.commit_failed",
            ) from error

        self._committed = True
        self._transaction_open = False
        self._atomic = None
        self._pending_events.clear()

        if not joined_ambient:
            publish_events()

    def rollback(self) -> None:
        """Rollback staged work, then begin a fresh bridge transaction."""

        self._ensure_writable()
        self._rollback_current_atomic()
        self._pending_events.clear()
        self._committed = False
        self._open_atomic()

    def _open_atomic(self) -> None:
        self._joined_ambient_transaction = transaction.get_connection().in_atomic_block
        atomic = transaction.atomic()
        try:
            atomic.__enter__()
        except DatabaseError as error:
            raise RepositoryError(
                "The Django transaction could not be started",
                code="django.transaction.begin_failed",
            ) from error
        self._atomic = atomic
        self._transaction_open = True

    def _rollback_current_atomic(self) -> None:
        atomic = self._require_atomic()
        signal = _RollbackSignal()
        try:
            atomic.__exit__(_RollbackSignal, signal, None)
        except DatabaseError as error:
            raise RepositoryError(
                "The Django transaction could not be rolled back",
                code="django.transaction.rollback_failed",
            ) from error
        finally:
            self._transaction_open = False
            self._atomic = None

    def _bind_repositories(self) -> None:
        self._contacts = DjangoContactRepository()
        self._external_identities = DjangoExternalIdentityRepository()
        self._organizations = DjangoOrganizationRepository()
        self._relationships = DjangoRelationshipRepository()

    def _unbind_repositories(self) -> None:
        self._contacts = None
        self._external_identities = None
        self._organizations = None
        self._relationships = None

    def _ensure_writable(self) -> None:
        if not self._active:
            raise InvalidStateError(
                "DjangoTransactionBridge must be entered before use",
                code="django.transaction.not_active",
            )
        if self._committed or not self._transaction_open:
            raise InvalidStateError(
                "DjangoTransactionBridge transaction is already committed",
                code="django.transaction.already_committed",
            )

    def _require_atomic(self) -> transaction.Atomic:
        assert self._atomic is not None
        return self._atomic


__all__ = ["DjangoTransactionBridge"]
