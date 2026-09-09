"""High-level transactional CRM facade."""

from __future__ import annotations

from collections.abc import Callable

from pycrmkit.config import CRMConfig, CRMContext
from pycrmkit.core.events import EventId
from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import InProcessEventBus
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.facade.activities import ActivitiesAPI
from pycrmkit.facade.audit import AuditAPI
from pycrmkit.facade.contacts import ContactsAPI
from pycrmkit.facade.custom_fields import CustomFieldsAPI
from pycrmkit.facade.events import EventsAPI
from pycrmkit.facade.leads import LeadsAPI
from pycrmkit.facade.opportunities import OpportunitiesAPI
from pycrmkit.facade.organizations import OrganizationsAPI
from pycrmkit.facade.pipelines import PipelinesAPI
from pycrmkit.facade.relationships import RelationshipsAPI
from pycrmkit.facade.tags import TagsAPI
from pycrmkit.facade.tasks import TasksAPI
from pycrmkit.facade.timeline import TimelineAPI
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork


class _Unset:
    __slots__ = ()


_UNSET = _Unset()


class CRM:
    """Headless CRM facade exposing transactional domain namespaces."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        event_bus: InProcessEventBus,
        config: CRMConfig | None = None,
        context: CRMContext | None = None,
        id_factory: IDFactory | None = None,
        clock: Clock | None = None,
    ) -> None:
        effective_config = config or CRMConfig()
        effective_context = context or CRMContext(
            actor_id=effective_config.default_actor_id,
            correlation_id=effective_config.default_correlation_id,
        )
        runtime = CRMRuntime(
            uow_factory=uow_factory,
            event_bus=event_bus,
            config=effective_config,
            context=effective_context,
            id_factory=id_factory or UUID4Factory(),
            clock=clock or SystemClock(),
        )
        self._runtime = runtime
        self.activities = ActivitiesAPI(runtime)
        self.contacts = ContactsAPI(runtime)
        self.leads = LeadsAPI(runtime)
        self.opportunities = OpportunitiesAPI(runtime)
        self.pipelines = PipelinesAPI(runtime)
        self.organizations = OrganizationsAPI(runtime)
        self.relationships = RelationshipsAPI(runtime)
        self.tasks = TasksAPI(runtime)
        self.timeline = TimelineAPI(runtime)
        self.tags = TagsAPI(runtime)
        self.custom_fields = CustomFieldsAPI(runtime)
        self.events = EventsAPI(event_bus)
        self.audit = AuditAPI(runtime)

    @classmethod
    def memory(
        cls,
        *,
        config: CRMConfig | None = None,
        context: CRMContext | None = None,
        id_factory: IDFactory | None = None,
        clock: Clock | None = None,
        event_bus: InProcessEventBus | None = None,
    ) -> CRM:
        """Create an isolated, fully wired in-memory CRM instance."""
        store = MemoryStore()
        bus = event_bus or InProcessEventBus()

        def uow_factory() -> UnitOfWork:
            return MemoryUnitOfWork(store, event_publisher=bus)

        return cls(
            uow_factory=uow_factory,
            event_bus=bus,
            config=config,
            context=context,
            id_factory=id_factory,
            clock=clock,
        )

    @property
    def config(self) -> CRMConfig:
        return self._runtime.config

    @property
    def context(self) -> CRMContext:
        return self._runtime.context

    def with_context(
        self,
        *,
        actor_id: str | None | _Unset = _UNSET,
        correlation_id: str | None | _Unset = _UNSET,
        causation_id: EventId | None | _Unset = _UNSET,
    ) -> CRM:
        """Return a lightweight facade view sharing storage/events with new context."""
        current = self.context
        context = CRMContext(
            actor_id=current.actor_id if isinstance(actor_id, _Unset) else actor_id,
            correlation_id=(
                current.correlation_id
                if isinstance(correlation_id, _Unset)
                else correlation_id
            ),
            causation_id=(
                current.causation_id
                if isinstance(causation_id, _Unset)
                else causation_id
            ),
        )
        return CRM(
            uow_factory=self._runtime.uow_factory,
            event_bus=self._runtime.event_bus,
            config=self.config,
            context=context,
            id_factory=self._runtime.id_factory,
            clock=self._runtime.clock,
        )
