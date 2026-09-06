"""Synchronous in-process event bus."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import TypeVar

from pycrmkit.core.events import EventType
from pycrmkit.events.envelope import DomainEvent
from pycrmkit.events.subscriber import EventHandler

HandlerT = TypeVar("HandlerT", bound=EventHandler)


class InProcessEventBus:
    """Deterministic synchronous bus for one Python process.

    Handlers run in subscription order. Handler failures propagate to the caller;
    retry, dead-letter, distributed delivery and durability are intentionally out
    of scope for the 0.1 foundation.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._lock = RLock()

    def subscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        """Subscribe a handler once for an exact event type."""

        key = EventType.parse(event_type)
        with self._lock:
            handlers = self._handlers.setdefault(key, [])
            if handler not in handlers:
                handlers.append(handler)

    def unsubscribe(self, event_type: EventType | str, handler: EventHandler) -> bool:
        """Remove one subscription and return whether it existed."""

        key = EventType.parse(event_type)
        with self._lock:
            handlers = self._handlers.get(key)
            if not handlers or handler not in handlers:
                return False
            handlers.remove(handler)
            if not handlers:
                self._handlers.pop(key, None)
            return True

    def on(self, event_type: EventType | str) -> Callable[[HandlerT], HandlerT]:
        """Decorator form of :meth:`subscribe`."""

        def decorator(handler: HandlerT) -> HandlerT:
            self.subscribe(event_type, handler)
            return handler

        return decorator

    def publish(self, event: DomainEvent) -> None:
        """Synchronously invoke current exact-type subscribers in stable order."""

        with self._lock:
            handlers = tuple(self._handlers.get(event.type, ()))
        for handler in handlers:
            handler(event)

    def clear(self) -> None:
        """Remove all subscriptions, primarily for test/process lifecycle control."""

        with self._lock:
            self._handlers.clear()
