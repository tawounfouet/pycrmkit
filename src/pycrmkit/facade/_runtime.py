"""Shared runtime for transactional facade namespaces."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import fields

from pycrmkit.activities import ActivityUpdate
from pycrmkit.audit import AuditService
from pycrmkit.config import CRMConfig, CRMContext
from pycrmkit.contacts import ContactUpdate
from pycrmkit.core.ids import IDFactory
from pycrmkit.core.time import Clock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.custom_fields import CustomFieldDefinitionRevision
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.organizations import OrganizationUpdate
from pycrmkit.relationships import RelationshipUpdate
from pycrmkit.tasks import TaskUpdate

Revision = (
    ActivityUpdate
    | TaskUpdate
    | ContactUpdate
    | OrganizationUpdate
    | RelationshipUpdate
    | CustomFieldDefinitionRevision
)


class CRMRuntime:
    """Dependency bundle shared by all facade namespaces."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        event_bus: InProcessEventBus,
        config: CRMConfig,
        context: CRMContext,
        id_factory: IDFactory,
        clock: Clock,
    ) -> None:
        self.uow_factory = uow_factory
        self.event_bus = event_bus
        self.config = config
        self.context = context
        self.id_factory = id_factory
        self.clock = clock

    def record_change(
        self,
        uow: UnitOfWork,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: object,
        changes: Mapping[str, object] | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> DomainEvent | None:
        """Stage one event/audit pair according to facade configuration."""
        if not self.config.events_enabled and not self.config.audit_enabled:
            return None
        event = DomainEvent.create(
            id_factory=self.id_factory,
            clock=self.clock,
            type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            actor_id=self.context.actor_id,
            correlation_id=self.context.correlation_id,
            causation_id=self.context.causation_id,
            payload=payload,
        )
        if self.config.audit_enabled:
            AuditService(
                uow.audit,
                id_factory=self.id_factory,
                clock=self.clock,
            ).record_event(event, changes=changes)
        if self.config.events_enabled:
            uow.add_event(event)
        return event


def present_fields(values: Mapping[str, object]) -> list[str]:
    """Return names of supplied non-empty fields without persisting their values."""
    return sorted(
        key
        for key, value in values.items()
        if value is not None and value != () and value != {}
    )


def revision_fields(value: Revision) -> list[str]:
    """Return explicitly supplied DTO field names without copying field values."""
    changed: list[str] = []
    for field_info in fields(value):
        current = getattr(value, field_info.name)
        if type(current).__name__ != "UnsetType":
            changed.append(field_info.name)
    return sorted(changed)
