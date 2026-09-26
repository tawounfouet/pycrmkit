"""SQLAlchemy Unit of Work with explicit transaction ownership."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pycrmkit.events.bus import InProcessEventBus
from pycrmkit.events.envelope import DomainEvent
from pycrmkit.events.publisher import EventPublisher
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.storage.sqlalchemy.errors import translate_sqlalchemy_error
from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemyActivityRepository,
    SQLAlchemyAuditRepository,
    SQLAlchemyCommunicationRepository,
    SQLAlchemyContactRepository,
    SQLAlchemyCustomFieldRepository,
    SQLAlchemyLeadRepository,
    SQLAlchemyOpportunityRepository,
    SQLAlchemyOrganizationRepository,
    SQLAlchemyPipelineRepository,
    SQLAlchemyRelationshipRepository,
    SQLAlchemyTagRepository,
    SQLAlchemyTaskRepository,
    SQLAlchemyTimelineRepository,
    SQLAlchemyWebhookDeliveryRepository,
    SQLAlchemyWebhookSubscriptionRepository,
)

SessionFactory = Callable[[], Session]


class SQLAlchemyUnitOfWork:
    """Explicit-commit Unit of Work over one shared SQLAlchemy Session.

    Repository adapters never commit independently. All repositories bound to
    this Unit of Work share the same Session and therefore the same database
    transaction. Domain events are staged until the database commit succeeds,
    then published synchronously as post-commit side effects.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.event_publisher = event_publisher or InProcessEventBus()
        self._session: Session | None = None
        self._active = False
        self._committed = False
        self._transaction_open = False
        self._pending_events: list[DomainEvent] = []

        self._activities: SQLAlchemyActivityRepository | None = None
        self._communications: SQLAlchemyCommunicationRepository | None = None
        self._contacts: SQLAlchemyContactRepository | None = None
        self._leads: SQLAlchemyLeadRepository | None = None
        self._opportunities: SQLAlchemyOpportunityRepository | None = None
        self._pipelines: SQLAlchemyPipelineRepository | None = None
        self._organizations: SQLAlchemyOrganizationRepository | None = None
        self._relationships: SQLAlchemyRelationshipRepository | None = None
        self._tasks: SQLAlchemyTaskRepository | None = None
        self._timeline: SQLAlchemyTimelineRepository | None = None
        self._tags: SQLAlchemyTagRepository | None = None
        self._custom_fields: SQLAlchemyCustomFieldRepository | None = None
        self._audit: SQLAlchemyAuditRepository | None = None
        self._webhooks: SQLAlchemyWebhookSubscriptionRepository | None = None
        self._webhook_deliveries: SQLAlchemyWebhookDeliveryRepository | None = None

    @property
    def activities(self) -> SQLAlchemyActivityRepository:
        self._ensure_active()
        assert self._activities is not None
        return self._activities

    @property
    def communications(self) -> SQLAlchemyCommunicationRepository:
        self._ensure_active()
        assert self._communications is not None
        return self._communications

    @property
    def contacts(self) -> SQLAlchemyContactRepository:
        self._ensure_active()
        assert self._contacts is not None
        return self._contacts

    @property
    def leads(self) -> SQLAlchemyLeadRepository:
        self._ensure_active()
        assert self._leads is not None
        return self._leads

    @property
    def opportunities(self) -> SQLAlchemyOpportunityRepository:
        self._ensure_active()
        assert self._opportunities is not None
        return self._opportunities

    @property
    def pipelines(self) -> SQLAlchemyPipelineRepository:
        self._ensure_active()
        assert self._pipelines is not None
        return self._pipelines

    @property
    def organizations(self) -> SQLAlchemyOrganizationRepository:
        self._ensure_active()
        assert self._organizations is not None
        return self._organizations

    @property
    def relationships(self) -> SQLAlchemyRelationshipRepository:
        self._ensure_active()
        assert self._relationships is not None
        return self._relationships

    @property
    def tasks(self) -> SQLAlchemyTaskRepository:
        self._ensure_active()
        assert self._tasks is not None
        return self._tasks

    @property
    def timeline(self) -> SQLAlchemyTimelineRepository:
        self._ensure_active()
        assert self._timeline is not None
        return self._timeline

    @property
    def tags(self) -> SQLAlchemyTagRepository:
        self._ensure_active()
        assert self._tags is not None
        return self._tags

    @property
    def custom_fields(self) -> SQLAlchemyCustomFieldRepository:
        self._ensure_active()
        assert self._custom_fields is not None
        return self._custom_fields

    @property
    def audit(self) -> SQLAlchemyAuditRepository:
        self._ensure_active()
        assert self._audit is not None
        return self._audit

    @property
    def webhooks(self) -> SQLAlchemyWebhookSubscriptionRepository:
        self._ensure_active()
        assert self._webhooks is not None
        return self._webhooks

    @property
    def webhook_deliveries(self) -> SQLAlchemyWebhookDeliveryRepository:
        self._ensure_active()
        assert self._webhook_deliveries is not None
        return self._webhook_deliveries

    @property
    def pending_events(self) -> tuple[DomainEvent, ...]:
        """Return the events currently staged for post-commit publication."""

        self._ensure_active()
        return tuple(self._pending_events)

    def add_event(self, event: DomainEvent) -> None:
        """Stage one immutable domain event for post-commit publication."""

        self._ensure_active()
        self._ensure_transaction_open()
        self._pending_events.append(event)

    def __enter__(self) -> Self:
        if self._active:
            raise InvalidStateError(
                "SQLAlchemyUnitOfWork is already active",
                code="sqlalchemy.uow.already_active",
            )
        self._session = self.session_factory()
        self._active = True
        self._committed = False
        self._transaction_open = True
        self._pending_events.clear()
        self._bind_repositories(self._session)
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

        session = self._require_session()
        try:
            if self._transaction_open and (exc_type is not None or not self._committed):
                session.rollback()
        finally:
            self._pending_events.clear()
            session.close()
            self._session = None
            self._transaction_open = False
            self._active = False
            self._unbind_repositories()
        return None

    def commit(self) -> None:
        """Commit all repositories atomically, then publish staged events."""

        self._ensure_active()
        self._ensure_transaction_open()
        if self._committed:
            raise InvalidStateError(
                "SQLAlchemyUnitOfWork transaction is already committed",
                code="sqlalchemy.uow.already_committed",
            )

        session = self._require_session()
        events = tuple(self._pending_events)
        try:
            session.commit()
        except SQLAlchemyError as error:
            session.rollback()
            self._pending_events.clear()
            raise translate_sqlalchemy_error(error) from error
        except BaseException:
            session.rollback()
            self._pending_events.clear()
            raise

        self._committed = True
        self._transaction_open = False
        self._pending_events.clear()

        for event in events:
            self.event_publisher.publish(event)

    def rollback(self) -> None:
        """Discard all uncommitted writes while keeping the UoW usable."""

        self._ensure_active()
        self._ensure_transaction_open()
        session = self._require_session()
        session.rollback()
        self._pending_events.clear()
        self._committed = False

    def _bind_repositories(self, session: Session) -> None:
        self._activities = SQLAlchemyActivityRepository(session)
        self._communications = SQLAlchemyCommunicationRepository(session)
        self._contacts = SQLAlchemyContactRepository(session)
        self._leads = SQLAlchemyLeadRepository(session)
        self._opportunities = SQLAlchemyOpportunityRepository(session)
        self._pipelines = SQLAlchemyPipelineRepository(session)
        self._organizations = SQLAlchemyOrganizationRepository(session)
        self._relationships = SQLAlchemyRelationshipRepository(session)
        self._tasks = SQLAlchemyTaskRepository(session)
        self._timeline = SQLAlchemyTimelineRepository(session)
        self._tags = SQLAlchemyTagRepository(session)
        self._custom_fields = SQLAlchemyCustomFieldRepository(session)
        self._audit = SQLAlchemyAuditRepository(session)
        self._webhooks = SQLAlchemyWebhookSubscriptionRepository(session)
        self._webhook_deliveries = SQLAlchemyWebhookDeliveryRepository(session)

    def _unbind_repositories(self) -> None:
        self._activities = None
        self._communications = None
        self._contacts = None
        self._leads = None
        self._opportunities = None
        self._pipelines = None
        self._organizations = None
        self._relationships = None
        self._tasks = None
        self._timeline = None
        self._tags = None
        self._custom_fields = None
        self._audit = None
        self._webhooks = None
        self._webhook_deliveries = None

    def _ensure_active(self) -> None:
        if not self._active:
            raise InvalidStateError(
                "SQLAlchemyUnitOfWork must be entered before use",
                code="sqlalchemy.uow.not_active",
            )

    def _ensure_transaction_open(self) -> None:
        if self._committed or not self._transaction_open:
            raise InvalidStateError(
                "SQLAlchemyUnitOfWork transaction is already committed",
                code="sqlalchemy.uow.already_committed",
            )

    def _require_session(self) -> Session:
        assert self._session is not None
        return self._session
