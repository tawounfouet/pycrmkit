"""Events facade namespace."""

from __future__ import annotations

from collections.abc import Callable

from pycrmkit.events import EventHandler, EventType, InProcessEventBus


class EventsAPI:
    """Subscription surface for events emitted by facade mutations."""

    def __init__(self, bus: InProcessEventBus) -> None:
        self._bus = bus

    def subscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        self._bus.subscribe(event_type, handler)

    def unsubscribe(self, event_type: EventType | str, handler: EventHandler) -> bool:
        return self._bus.unsubscribe(event_type, handler)

    def on(self, event_type: EventType | str) -> Callable[[EventHandler], EventHandler]:
        return self._bus.on(event_type)
