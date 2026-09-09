"""Internal state containers for the in-memory persistence adapter."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock

from pycrmkit.activities.entities import Activity, ActivityId
from pycrmkit.audit.entries import AuditEntry, AuditEntryId
from pycrmkit.contacts.entities import Contact, ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields.entities import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldValue,
)
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.leads import Lead, LeadId
from pycrmkit.opportunities import Opportunity, OpportunityId
from pycrmkit.organizations.entities import Organization, OrganizationId
from pycrmkit.pipelines import Pipeline
from pycrmkit.relationships.entities import Relationship, RelationshipId
from pycrmkit.tags.entities import Tag, TagAssignment, TagId
from pycrmkit.tasks.entities import Task, TaskId
from pycrmkit.timeline.entries import TimelineEntry, TimelineEntryId


@dataclass(slots=True)
class _MemoryState:
    activities: dict[ActivityId, Activity] = field(default_factory=dict)
    contacts: dict[ContactId, Contact] = field(default_factory=dict)
    leads: dict[LeadId, Lead] = field(default_factory=dict)
    opportunities: dict[OpportunityId, Opportunity] = field(default_factory=dict)
    pipelines: dict[str, Pipeline] = field(default_factory=dict)
    organizations: dict[OrganizationId, Organization] = field(default_factory=dict)
    relationships: dict[RelationshipId, Relationship] = field(default_factory=dict)
    tasks: dict[TaskId, Task] = field(default_factory=dict)
    timeline_entries: dict[TimelineEntryId, TimelineEntry] = field(default_factory=dict)
    tags: dict[TagId, Tag] = field(default_factory=dict)
    tag_assignments: dict[tuple[TagId, EntityReference], TagAssignment] = field(
        default_factory=dict
    )
    custom_field_definitions: dict[
        CustomFieldDefinitionId, list[CustomFieldDefinition]
    ] = field(default_factory=dict)
    custom_field_values: dict[
        tuple[CustomFieldDefinitionId, EntityReference], CustomFieldValue
    ] = field(default_factory=dict)
    audit_entries: dict[AuditEntryId, AuditEntry] = field(default_factory=dict)

    def clone(self) -> _MemoryState:
        """Return a transaction-safe deep copy of all persisted state."""
        return deepcopy(self)


class MemoryStore:
    """Committed in-process state shared by one or more MemoryUnitOfWork instances."""

    def __init__(self) -> None:
        self._state = _MemoryState()
        self._lock = RLock()
        self._uow_active = False

    def _snapshot(self) -> _MemoryState:
        with self._lock:
            return self._state.clone()

    def _begin(self) -> _MemoryState:
        with self._lock:
            if self._uow_active:
                raise InvalidStateError(
                    "nested or concurrent MemoryUnitOfWork transactions are not supported",
                    code="memory.uow.already_active",
                )
            self._uow_active = True
            return self._state.clone()

    def _commit(self, state: _MemoryState) -> None:
        with self._lock:
            self._state = state.clone()

    def _end(self) -> None:
        with self._lock:
            self._uow_active = False
