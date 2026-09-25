"""Stable registry-governed event serialization tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from pycrmkit.core.events import EventId
from pycrmkit.events import DomainEvent, EventRegistry, EventSerializer
from pycrmkit.exceptions import NotFoundError, ValidationError


def _event(
    event_type: str = "contact.created",
    schema_version: int = 1,
) -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID("00000000-0000-0000-0000-000000000501")),
        type=event_type,  # type: ignore[arg-type]
        schema_version=schema_version,
        aggregate_type="contact",
        aggregate_id="00000000-0000-0000-0000-000000000601",
        occurred_at=datetime(2026, 9, 25, 20, 0, tzinfo=UTC),
        actor_id="user-1",
        correlation_id="corr-1",
        payload={"z": 2, "a": ["é", True]},
        metadata={"source": "tests"},
    )


def test_serializer_produces_canonical_json_and_round_trips() -> None:
    registry = EventRegistry()
    registry.register("contact.created", 1)
    serializer = EventSerializer(registry)

    encoded = serializer.dumps(_event())
    decoded = serializer.loads(encoded)

    assert encoded == json.dumps(
        _event().to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert decoded.to_dict() == _event().to_dict()


def test_serializer_rejects_unregistered_type_or_version() -> None:
    registry = EventRegistry()
    registry.register("contact.created", 1)
    serializer = EventSerializer(registry)

    with pytest.raises(NotFoundError):
        serializer.dumps(_event("contact.updated", 1))
    with pytest.raises(NotFoundError):
        serializer.dumps(_event("contact.created", 2))


def test_serializer_rejects_invalid_json_and_non_object_envelope() -> None:
    serializer = EventSerializer(EventRegistry())

    with pytest.raises(ValidationError) as malformed:
        serializer.loads("{")
    assert malformed.value.code == "event.serialization.invalid_json"

    with pytest.raises(ValidationError) as non_object:
        serializer.loads("[]")
    assert non_object.value.code == "event.serialization.invalid_envelope"


def test_canonical_contact_created_v1_fixture_is_stable() -> None:
    registry = EventRegistry()
    registry.register("contact.created", 1)
    serializer = EventSerializer(registry)
    fixture = Path("tests/fixtures/events/contact-created-v1.canonical.json")

    assert serializer.dumps(
        DomainEvent.from_dict(
            json.loads(
                Path("tests/fixtures/events/contact-created-v1.json").read_text(
                    encoding="utf-8"
                )
            )
        )
    ) == fixture.read_text(encoding="utf-8")
