"""Run Activity repository contracts against the official SQLAlchemy adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.activities import (
    Activity,
    ActivityId,
    ActivityParticipant,
    ActivityRepository,
    ActivityType,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.organizations import OrganizationId
from sqlalchemy.orm import Session

from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyActivityRepository

from ...contracts.activities_repository import ActivityRepositoryContract

NOW = datetime(2026, 9, 7, 9, 0, tzinfo=UTC)


@pytest.fixture
def participant_reference() -> EntityReference:
    return EntityReference(
        "contact",
        ContactId(UUID("00000000-0000-4000-8000-000000000301")),
    )


@pytest.fixture
def related_reference() -> EntityReference:
    return EntityReference(
        "organization",
        OrganizationId(UUID("00000000-0000-4000-8000-000000000302")),
    )


@pytest.fixture
def repository(session: Session) -> ActivityRepository:
    repository = SQLAlchemyActivityRepository(session)
    assert isinstance(repository, ActivityRepository)
    return repository


@pytest.fixture
def activity(participant_reference, related_reference) -> Activity:
    return Activity(
        id=ActivityId(UUID("00000000-0000-4000-8000-000000000311")),
        created_at=NOW,
        updated_at=NOW,
        type=ActivityType.CALL,
        occurred_at=NOW - timedelta(hours=1),
        subject="Customer call",
        participants=(ActivityParticipant(participant_reference, is_primary=True),),
        references=(related_reference,),
    )


@pytest.fixture
def second_activity() -> Activity:
    return Activity(
        id=ActivityId(UUID("00000000-0000-4000-8000-000000000312")),
        created_at=NOW,
        updated_at=NOW,
        type=ActivityType.NOTE,
        occurred_at=NOW,
        description="Internal note",
    )


@pytest.fixture
def missing_activity_id() -> ActivityId:
    return ActivityId(UUID("00000000-0000-4000-8000-000000009999"))


class TestSQLAlchemyActivityRepository(ActivityRepositoryContract):
    """Official SQLAlchemy adapter must satisfy the reusable Activity contract."""

