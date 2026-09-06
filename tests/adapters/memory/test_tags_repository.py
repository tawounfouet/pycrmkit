"""Run Tag repository contracts against the official Memory adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pycrmkit.storage.memory import MemoryTagRepository
from pycrmkit.tags.entities import Tag, TagId
from pycrmkit.tags.value_objects import TagName
from ...contracts.tags_repository import assert_tag_repository_contract

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def test_memory_tag_repository_passes_contract() -> None:
    assert_tag_repository_contract(MemoryTagRepository())


def test_tag_repository_isolates_mutations() -> None:
    repository = MemoryTagRepository()
    tag = Tag(
        id=TagId(UUID(int=1)),
        created_at=NOW,
        updated_at=NOW,
        name=TagName("VIP"),
        metadata={"tier": "gold"},
    )
    repository.save(tag)
    tag.metadata["tier"] = "changed"
    assert repository.get(tag.id).metadata == {"tier": "gold"}

    loaded = repository.get(tag.id)
    loaded.metadata["tier"] = "changed-again"
    assert repository.get(tag.id).metadata == {"tier": "gold"}
