"""Publisher contract for CRM domain events."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.events.envelope import DomainEvent


@runtime_checkable
class EventPublisher(Protocol):
    """Minimal backend-neutral event publication contract."""

    def publish(self, event: DomainEvent) -> None:
        """Publish one event to subscribed handlers."""
