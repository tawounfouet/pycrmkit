"""Domain-event envelope and compatibility tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import UUID

import pytest

from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.exceptions import ValidationError

IdT = TypeVar("IdT", bound=UUIDId)


class DeterministicIdFactory:
    def new(self, id_type: type[IdT]) -> IdT:
        return id_type(UUID("00000000-0000-0000-0000-000000000101"))


def _event() -> DomainEvent:
    return DomainEvent.create(
        id_factory=DeterministicIdFactory(),
        clock=FixedClock(datetime(2026, 9, 6, 18, 0, tzinfo=UTC)),
        type="contact.created",
        aggregate_type="Contact",
        aggregate_id="00000000-0000-0000-0000-000000000201",
        actor_id="user_123",
        correlation_id="corr-001",
        payload={"source": "import", "labels": ["vip", "new"]},
        metadata={"origin": "tests"},
    )


def test_event_type_requires_dotted_lowercase_name() -> None:
    assert str(EventType(" Contact.Created ")) == "contact.created"
    with pytest.raises(ValidationError):
        EventType("created")


def test_domain_event_is_versioned_utc_and_deeply_immutable() -> None:
    event = _event()
    assert event.schema_version == 1
    assert event.occurred_at.tzinfo is UTC
    assert event.aggregate_type == "contact"
    with pytest.raises(TypeError):
        event.payload["source"] = "changed"  # type: ignore[index]
    labels = event.payload["labels"]
    assert isinstance(labels, tuple)


def test_domain_event_rejects_invalid_json_payload_and_schema_version() -> None:
    with pytest.raises(ValidationError):
        DomainEvent(
            id=EventId(UUID(int=1)),
            type=EventType("contact.created"),
            schema_version=0,
            aggregate_type="contact",
            aggregate_id="1",
            occurred_at=datetime.now(UTC),
        )
    with pytest.raises(ValidationError):
        DomainEvent(
            id=EventId(UUID(int=1)),
            type=EventType("contact.created"),
            schema_version=1,
            aggregate_type="contact",
            aggregate_id="1",
            occurred_at=datetime.now(UTC),
            payload={"bad": object()},
        )


def test_event_serialization_round_trip_preserves_public_envelope() -> None:
    event = _event()
    serialized = event.to_dict()
    restored = DomainEvent.from_dict(serialized)
    assert restored.to_dict() == serialized


def test_contact_created_v1_fixture_is_stable() -> None:
    fixture = Path("tests/fixtures/events/contact-created-v1.json")
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    assert _event().to_dict() == expected
