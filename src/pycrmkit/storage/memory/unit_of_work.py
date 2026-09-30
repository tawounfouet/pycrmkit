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
from pycrmkit.storage.memory.campaign_audience import MemoryCampaignAudienceRepository
from pycrmkit.storage.memory.campaign_linkage import MemoryCampaignLinkageRepository
from pycrmkit.storage.memory.campaigns import MemoryCampaignRepository
from pycrmkit.storage.memory.communication import MemoryCommunicationRepository
from pycrmkit.storage.memory.contacts import MemoryContactRepository
from pycrmkit.storage.memory.custom_fields import MemoryCustomFieldRepository
from pycrmkit.storage.memory.external_identities import MemoryExternalIdentityRepository
from pycrmkit.storage.memory.leads import MemoryLeadRepository
from pycrmkit.storage.memory.opportunities import MemoryOpportunityRepository
from pycrmkit.storage.memory.organizations import MemoryOrganizationRepository
from pycrmkit.storage.memory.pipelines import MemoryPipelineRepository
from pycrmkit.storage.memory.relationships import MemoryRelationshipRepository
from pycrmkit.storage.memory.saved_queries import MemorySavedQueryRepository
from pycrmkit.storage.memory.segments import (
    MemorySegmentMembershipRepository,
    MemorySegmentQueryExecutor,
    MemorySegmentRepository,
)
from pycrmkit.storage.memory.tags import MemoryTagRepository
from pycrmkit.storage.memory.tasks import MemoryTaskRepository
from pycrmkit.storage.memory.timeline import MemoryTimelineRepository
from pycrmkit.storage.memory.webhook_deliveries import MemoryWebhookDeliveryRepository
from pycrmkit.storage.memory.webhooks import MemoryWebhookSubscriptionRepository


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
        self._store_transaction_open = False
        self._working: _MemoryState | None = None
        self._activities: MemoryActivityRepository | None = None
        self._communications: MemoryCommunicationRepository | None = None
        self._campaigns: MemoryCampaignRepository | None = None
        self._campaign_audience: MemoryCampaignAudienceRepository | None = None
        self._campaign_linkage: MemoryCampaignLinkageRepository | None = None
        self._contacts: MemoryContactRepository | None = None
        self._leads: MemoryLeadRepository | None = None
        self._opportunities: MemoryOpportunityRepository | None = None
        self._pipelines: MemoryPipelineRepository | None = None
        self._organizations: MemoryOrganizationRepository | None = None
        self._relationships: MemoryRelationshipRepository | None = None
        self._tasks: MemoryTaskRepository | None = None
        self._segments: MemorySegmentRepository | None = None
        self._saved_queries: MemorySavedQueryRepository | None = None
        self._segment_memberships: MemorySegmentMembershipRepository | None = None
        self._segment_query_executor: MemorySegmentQueryExecutor | None = None
        self._timeline: MemoryTimelineRepository | None = None
        self._tags: MemoryTagRepository | None = None
        self._custom_fields: MemoryCustomFieldRepository | None = None
        self._external_identities: MemoryExternalIdentityRepository | None = None
        self._audit: MemoryAuditRepository | None = None
        self._webhooks: MemoryWebhookSubscriptionRepository | None = None
        self._webhook_deliveries: MemoryWebhookDeliveryRepository | None = None
        self._pending_events: list[DomainEvent] = []

    @property
    def activities(self) -> MemoryActivityRepository:
        self._ensure_active()
        assert self._activities is not None
        return self._activities

    @property
    def communications(self) -> MemoryCommunicationRepository:
        self._ensure_active()
        assert self._communications is not None
        return self._communications

    @property
    def campaigns(self) -> MemoryCampaignRepository:
        self._ensure_active()
        assert self._campaigns is not None
        return self._campaigns

    @property
    def campaign_audience(self) -> MemoryCampaignAudienceRepository:
        self._ensure_active()
        assert self._campaign_audience is not None
        return self._campaign_audience

    @property
    def campaign_linkage(self) -> MemoryCampaignLinkageRepository:
        self._ensure_active()
        assert self._campaign_linkage is not None
        return self._campaign_linkage

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
    def opportunities(self) -> MemoryOpportunityRepository:
        self._ensure_active()
        assert self._opportunities is not None
        return self._opportunities

    @property
    def pipelines(self) -> MemoryPipelineRepository:
        self._ensure_active()
        assert self._pipelines is not None
        return self._pipelines

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
    def segments(self) -> MemorySegmentRepository:
        self._ensure_active()
        assert self._segments is not None
        return self._segments

    @property
    def saved_queries(self) -> MemorySavedQueryRepository:
        self._ensure_active()
        assert self._saved_queries is not None
        return self._saved_queries

    @property
    def segment_memberships(self) -> MemorySegmentMembershipRepository:
        self._ensure_active()
        assert self._segment_memberships is not None
        return self._segment_memberships

    @property
    def segment_query_executor(self) -> MemorySegmentQueryExecutor:
        self._ensure_active()
        assert self._segment_query_executor is not None
        return self._segment_query_executor

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
    def external_identities(self) -> MemoryExternalIdentityRepository:
        self._ensure_active()
        assert self._external_identities is not None
        return self._external_identities

    @property
    def audit(self) -> MemoryAuditRepository:
        self._ensure_active()
        assert self._audit is not None
        return self._audit

    @property
    def webhooks(self) -> MemoryWebhookSubscriptionRepository:
        self._ensure_active()
        assert self._webhooks is not None
        return self._webhooks

    @property
    def webhook_deliveries(self) -> MemoryWebhookDeliveryRepository:
        self._ensure_active()
        assert self._webhook_deliveries is not None
        return self._webhook_deliveries

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
        self._store_transaction_open = True
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
        if self._store_transaction_open:
            if exc_type is not None or not self._committed:
                self._discard_working_state()
            self.store._end()
            self._store_transaction_open = False
        self._pending_events.clear()
        self._active = False
        return None

    def commit(self) -> None:
        self._ensure_active()
        if self._committed or not self._store_transaction_open:
            raise InvalidStateError(
                "MemoryUnitOfWork transaction is already committed",
                code="memory.uow.already_committed",
            )
        assert self._working is not None
        events = tuple(self._pending_events)
        self.store._commit(self._working)
        self._committed = True
        self._pending_events.clear()

        # Release the MemoryStore transaction before synchronous post-commit
        # subscribers run. This lets subscribers open a fresh UoW against the
        # newly committed state without creating a nested transaction.
        self.store._end()
        self._store_transaction_open = False

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
        self._communications = MemoryCommunicationRepository(state)
        self._campaigns = MemoryCampaignRepository(state)
        self._campaign_audience = MemoryCampaignAudienceRepository(state)
        self._campaign_linkage = MemoryCampaignLinkageRepository(state)
        self._contacts = MemoryContactRepository(state)
        self._leads = MemoryLeadRepository(state)
        self._opportunities = MemoryOpportunityRepository(state)
        self._pipelines = MemoryPipelineRepository(state)
        self._organizations = MemoryOrganizationRepository(state)
        self._relationships = MemoryRelationshipRepository(state)
        self._tasks = MemoryTaskRepository(state)
        self._segments = MemorySegmentRepository(state)
        self._saved_queries = MemorySavedQueryRepository(state)
        self._segment_memberships = MemorySegmentMembershipRepository(state)
        self._segment_query_executor = MemorySegmentQueryExecutor(state)
        self._timeline = MemoryTimelineRepository(state)
        self._tags = MemoryTagRepository(state)
        self._custom_fields = MemoryCustomFieldRepository(state)
        self._external_identities = MemoryExternalIdentityRepository(state)
        self._audit = MemoryAuditRepository(state)
        self._webhooks = MemoryWebhookSubscriptionRepository(state)
        self._webhook_deliveries = MemoryWebhookDeliveryRepository(state)

    def _ensure_active(self) -> None:
        if not self._active:
            raise InvalidStateError(
                "MemoryUnitOfWork must be entered before use",
                code="memory.uow.not_active",
            )
