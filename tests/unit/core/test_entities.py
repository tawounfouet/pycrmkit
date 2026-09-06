from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime, timedelta, timezone

import pytest

from pycrmkit.core import Entity, EntityId, TimestampedEntity, ValueObject


@dataclass(eq=False, slots=True)
class ExampleEntity(Entity[EntityId]):
    name: str


@dataclass(eq=False, slots=True)
class OtherEntity(Entity[EntityId]):
    name: str


@dataclass(eq=False, slots=True)
class ExampleTimestampedEntity(TimestampedEntity[EntityId]):
    name: str


@dataclass(frozen=True, slots=True)
class EmailValue(ValueObject):
    value: str


def test_entity_equality_is_based_on_type_and_identity() -> None:
    entity_id = EntityId.parse("12345678-1234-5678-1234-567812345678")

    first = ExampleEntity(entity_id, "before")
    second = ExampleEntity(entity_id, "after")
    other_type = OtherEntity(entity_id, "before")

    assert first == second
    assert hash(first) == hash(second)
    assert first != other_type


def test_timestamped_entity_normalizes_timestamps_to_utc() -> None:
    offset = timezone(timedelta(hours=2))
    entity = ExampleTimestampedEntity(
        EntityId.parse("12345678-1234-5678-1234-567812345678"),
        created_at=datetime(2026, 9, 6, 10, 0, tzinfo=offset),
        updated_at=datetime(2026, 9, 6, 11, 0, tzinfo=offset),
        name="example",
    )

    assert entity.created_at == datetime(2026, 9, 6, 8, 0, tzinfo=UTC)
    assert entity.updated_at == datetime(2026, 9, 6, 9, 0, tzinfo=UTC)


def test_timestamped_entity_rejects_invalid_order() -> None:
    with pytest.raises(ValueError, match="updated_at"):
        ExampleTimestampedEntity(
            EntityId.parse("12345678-1234-5678-1234-567812345678"),
            created_at=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 9, 6, 9, 0, tzinfo=UTC),
            name="example",
        )


def test_value_object_subclasses_are_value_semantic_and_immutable() -> None:
    first = EmailValue("user@example.com")
    second = EmailValue("user@example.com")

    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.value = "other@example.com"  # type: ignore[misc]
