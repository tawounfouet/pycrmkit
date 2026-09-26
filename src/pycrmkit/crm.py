"""High-level transactional CRM facade."""

from __future__ import annotations

from collections.abc import Callable

from pycrmkit.communication import CommunicationAddress, EmailProvider, TemplateRenderer
from pycrmkit.config import CRMConfig, CRMContext
from pycrmkit.core.events import EventId
from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import DomainEvent, EventRegistry, InProcessEventBus, default_event_registry
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.facade.activities import ActivitiesAPI
from pycrmkit.facade.audit import AuditAPI
from pycrmkit.facade.contacts import ContactsAPI
from pycrmkit.facade.custom_fields import CustomFieldsAPI
from pycrmkit.facade.email import EmailAPI
from pycrmkit.facade.events import EventsAPI
from pycrmkit.facade.leads import LeadsAPI
from pycrmkit.facade.opportunities import OpportunitiesAPI
from pycrmkit.facade.organizations import OrganizationsAPI
from pycrmkit.facade.pipelines import PipelinesAPI
from pycrmkit.facade.relationships import RelationshipsAPI
from pycrmkit.facade.tags import TagsAPI
from pycrmkit.facade.tasks import TasksAPI
from pycrmkit.facade.timeline import TimelineAPI
from pycrmkit.facade.webhooks import WebhooksAPI
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork
from pycrmkit.webhooks import (
    StdlibWebhookTransport,
    WebhookRetryPolicy,
    WebhookTransport,
)
from pycrmkit.webhooks.integration import WebhookEventBridge


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
        email_provider: EmailProvider | None = None,
        email_sender: CommunicationAddress | None = None,
        template_renderer: TemplateRenderer | None = None,
        event_registry: EventRegistry | None = None,
        webhook_transport: WebhookTransport | None = None,
        webhook_retry_policy: WebhookRetryPolicy | None = None,
        webhook_timeout_seconds: float = 10.0,
        webhook_auto_delivery: bool = True,
        _webhook_bridge: WebhookEventBridge | None = None,
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
        self._email_provider = email_provider
        self._email_sender = email_sender
        self._template_renderer = template_renderer
        self._event_registry = event_registry or default_event_registry()
        self._webhook_transport = webhook_transport or StdlibWebhookTransport()
        self._webhook_retry_policy = webhook_retry_policy or WebhookRetryPolicy()
        self._webhook_timeout_seconds = webhook_timeout_seconds
        self._webhook_auto_delivery = webhook_auto_delivery
        self.activities = ActivitiesAPI(runtime)
        self.email = EmailAPI(runtime, provider=email_provider, sender=email_sender, renderer=template_renderer)
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
        self.webhooks = WebhooksAPI(
            runtime,
            registry=self._event_registry,
            transport=self._webhook_transport,
            retry_policy=self._webhook_retry_policy,
            timeout_seconds=self._webhook_timeout_seconds,
        )
        self._webhook_bridge = _webhook_bridge
        if self._webhook_bridge is None and self._webhook_auto_delivery:
            self._webhook_bridge = WebhookEventBridge(
                event_bus=event_bus,
                registry=self._event_registry,
                deliver=self.webhooks.deliver,
            )
            self._webhook_bridge.install()

    @classmethod
    def memory(
        cls,
        *,
        config: CRMConfig | None = None,
        context: CRMContext | None = None,
        id_factory: IDFactory | None = None,
        clock: Clock | None = None,
        event_bus: InProcessEventBus | None = None,
        email_provider: EmailProvider | None = None,
        email_sender: CommunicationAddress | None = None,
        template_renderer: TemplateRenderer | None = None,
        event_registry: EventRegistry | None = None,
        webhook_transport: WebhookTransport | None = None,
        webhook_retry_policy: WebhookRetryPolicy | None = None,
        webhook_timeout_seconds: float = 10.0,
        webhook_auto_delivery: bool = True,
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
            email_provider=email_provider,
            email_sender=email_sender,
            template_renderer=template_renderer,
            event_registry=event_registry,
            webhook_transport=webhook_transport,
            webhook_retry_policy=webhook_retry_policy,
            webhook_timeout_seconds=webhook_timeout_seconds,
            webhook_auto_delivery=webhook_auto_delivery,
        )

    @property
    def config(self) -> CRMConfig:
        return self._runtime.config

    @property
    def context(self) -> CRMContext:
        return self._runtime.context

    def with_event(self, event: DomainEvent) -> CRM:
        """Return a facade view for work causally triggered by a parent event."""

        context = CRMContext.from_event(event)
        return CRM(
            uow_factory=self._runtime.uow_factory,
            event_bus=self._runtime.event_bus,
            config=self.config,
            context=context,
            id_factory=self._runtime.id_factory,
            clock=self._runtime.clock,
            email_provider=self._email_provider,
            email_sender=self._email_sender,
            template_renderer=self._template_renderer,
            event_registry=self._event_registry,
            webhook_transport=self._webhook_transport,
            webhook_retry_policy=self._webhook_retry_policy,
            webhook_timeout_seconds=self._webhook_timeout_seconds,
            webhook_auto_delivery=self._webhook_auto_delivery,
            _webhook_bridge=self._webhook_bridge,
        )

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
            email_provider=self._email_provider,
            email_sender=self._email_sender,
            template_renderer=self._template_renderer,
            event_registry=self._event_registry,
            webhook_transport=self._webhook_transport,
            webhook_retry_policy=self._webhook_retry_policy,
            webhook_timeout_seconds=self._webhook_timeout_seconds,
            webhook_auto_delivery=self._webhook_auto_delivery,
            _webhook_bridge=self._webhook_bridge,
        )
