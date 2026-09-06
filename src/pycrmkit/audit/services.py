"""Application service for explicit, privacy-conscious audit recording."""

from __future__ import annotations

from collections.abc import Mapping

from pycrmkit.audit.entries import AuditEntry, AuditEntryId
from pycrmkit.audit.repository import AuditRepository
from pycrmkit.core.ids import IDFactory
from pycrmkit.core.time import Clock
from pycrmkit.events.envelope import DomainEvent


class AuditService:
    """Create append-only audit records using injected repository/time/ID dependencies."""

    def __init__(
        self,
        repository: AuditRepository,
        *,
        id_factory: IDFactory,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.id_factory = id_factory
        self.clock = clock

    def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: object,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        changes: Mapping[str, object] | None = None,
    ) -> AuditEntry:
        """Create and append one audit entry.

        ``changes`` is explicit rather than inferred from an entity/event so callers
        can apply PII minimization before audit persistence.
        """

        entry = AuditEntry(
            id=self.id_factory.new(AuditEntryId),
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            occurred_at=self.clock.now(),
            changes=changes or {},
            correlation_id=correlation_id,
        )
        self.repository.append(entry)
        return entry

    def record_event(
        self,
        event: DomainEvent,
        *,
        changes: Mapping[str, object] | None = None,
        action: str | None = None,
    ) -> AuditEntry:
        """Record audit context from an event without copying event payload by default."""

        return self.record(
            action=action or str(event.type),
            entity_type=event.aggregate_type,
            entity_id=event.aggregate_id,
            actor_id=event.actor_id,
            correlation_id=event.correlation_id,
            changes=changes,
        )
