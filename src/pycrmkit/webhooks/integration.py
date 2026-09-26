"""Bridge committed CRM domain events into webhook delivery."""

from __future__ import annotations

from collections.abc import Callable

from pycrmkit.core.events import EventType
from pycrmkit.events import DomainEvent, EventRegistry, InProcessEventBus


class WebhookEventBridge:
    """Subscribe registered public event types to automatic webhook delivery."""

    def __init__(
        self,
        *,
        event_bus: InProcessEventBus,
        registry: EventRegistry,
        deliver: Callable[[DomainEvent], object],
    ) -> None:
        self._event_bus = event_bus
        self._registry = registry
        self._deliver = deliver
        self._handler = self._handle_event
        self._installed_event_types: tuple[EventType, ...] = ()

    @property
    def installed(self) -> bool:
        return bool(self._installed_event_types)

    def install(self) -> None:
        """Install exact-type subscriptions once for the current registry."""

        if self.installed:
            return
        event_types = tuple(
            sorted(
                {definition.event_type for definition in self._registry.definitions()},
                key=str,
            )
        )
        for event_type in event_types:
            self._event_bus.subscribe(event_type, self._handler)
        self._installed_event_types = event_types

    def uninstall(self) -> None:
        """Remove bridge subscriptions without clearing unrelated handlers."""

        for event_type in self._installed_event_types:
            self._event_bus.unsubscribe(event_type, self._handler)
        self._installed_event_types = ()

    def _handle_event(self, event: DomainEvent) -> None:
        self._registry.validate(event)
        self._deliver(event)


__all__ = ["WebhookEventBridge"]
