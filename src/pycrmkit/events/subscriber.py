"""Subscriber typing for in-process CRM event handlers."""

from __future__ import annotations

from typing import Protocol

from pycrmkit.events.envelope import DomainEvent


class EventHandler(Protocol):
    """Callable invoked for a matching DomainEvent."""

    def __call__(self, event: DomainEvent) -> None:
        """Handle one event."""
