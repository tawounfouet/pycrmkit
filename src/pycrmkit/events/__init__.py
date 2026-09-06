"""CRM domain-event foundation."""

from pycrmkit.core.events import EventId, EventType
from pycrmkit.events.bus import InProcessEventBus
from pycrmkit.events.envelope import DomainEvent
from pycrmkit.events.publisher import EventPublisher
from pycrmkit.events.subscriber import EventHandler

__all__ = [
    "DomainEvent",
    "EventHandler",
    "EventId",
    "EventPublisher",
    "EventType",
    "InProcessEventBus",
]
