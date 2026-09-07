"""Backend-independent Unit of Work contract."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from pycrmkit.activities.repository import ActivityRepository
from pycrmkit.audit.repository import AuditRepository
from pycrmkit.contacts.repository import ContactRepository
from pycrmkit.custom_fields.repository import CustomFieldRepository
from pycrmkit.events.envelope import DomainEvent
from pycrmkit.organizations.repository import OrganizationRepository
from pycrmkit.relationships.repository import RelationshipRepository
from pycrmkit.tags.repository import TagRepository
from pycrmkit.tasks.repository import TaskRepository
from pycrmkit.timeline.repository import TimelineRepository


class UnitOfWork(Protocol):
    """Transactional repository grouping used by application services and workflows."""

    @property
    def activities(self) -> ActivityRepository:
        """Activities participating in the current transaction."""

    @property
    def contacts(self) -> ContactRepository:
        """Contacts participating in the current transaction."""

    @property
    def organizations(self) -> OrganizationRepository:
        """Organizations participating in the current transaction."""

    @property
    def relationships(self) -> RelationshipRepository:
        """Relationships participating in the current transaction."""

    @property
    def tasks(self) -> TaskRepository:
        """Tasks participating in the current transaction."""

    @property
    def timeline(self) -> TimelineRepository:
        """Customer-facing timeline projections participating in the transaction."""

    @property
    def tags(self) -> TagRepository:
        """Tags participating in the current transaction."""

    @property
    def custom_fields(self) -> CustomFieldRepository:
        """Custom fields participating in the current transaction."""

    @property
    def audit(self) -> AuditRepository:
        """Audit entries participating atomically in the current transaction."""

    def add_event(self, event: DomainEvent) -> None:
        """Stage a domain event for post-commit dispatch."""

    def commit(self) -> None:
        """Atomically persist the current transaction state."""

    def rollback(self) -> None:
        """Discard uncommitted transaction changes."""

    def __enter__(self) -> Self:
        """Enter a transaction context."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Close the transaction, rolling back uncommitted work."""
