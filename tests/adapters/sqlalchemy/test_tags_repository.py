"""Run Tag repository contracts against the SQLAlchemy adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyTagRepository
from pycrmkit.tags.entities import Tag, TagId
from pycrmkit.tags.value_objects import TagName

from ...contracts.tags_repository import assert_tag_repository_contract

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def test_sqlalchemy_tag_repository_passes_contract(session: Session) -> None:
    assert_tag_repository_contract(SQLAlchemyTagRepository(session))


def test_tag_repository_isolates_mutations(session: Session) -> None:
    repository = SQLAlchemyTagRepository(session)
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
