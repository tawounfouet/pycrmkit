"""CRM domain-event foundation."""

from pycrmkit.core.events import EventId, EventType
from pycrmkit.events.bus import InProcessEventBus
from pycrmkit.events.envelope import DomainEvent
from pycrmkit.events.publisher import EventPublisher
from pycrmkit.events.registry import (
    BUILTIN_EVENT_TYPES,
    EventDefinition,
    EventRegistry,
    default_event_registry,
)
from pycrmkit.events.serializer import EventSerializer
from pycrmkit.events.subscriber import EventHandler

__all__ = [
    "BUILTIN_EVENT_TYPES",
    "DomainEvent",
    "EventDefinition",
    "EventHandler",
    "EventId",
    "EventPublisher",
    "EventRegistry",
    "EventSerializer",
    "EventType",
    "InProcessEventBus",
    "default_event_registry",
]
