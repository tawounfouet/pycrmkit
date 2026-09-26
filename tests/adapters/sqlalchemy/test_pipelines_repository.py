from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from pycrmkit.pipelines import Pipeline, PipelineRepository, Stage, StageTransition
from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyPipelineRepository

from ...contracts.pipelines_repository import PipelineRepositoryContract


def build_pipeline(pipeline_id: str, name: str) -> Pipeline:
    return Pipeline(
        id=pipeline_id,
        name=name,
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("won", "Won", 10, terminal=True, outcome="won"),
        ),
        transitions=(StageTransition("new", "won"),),
    )


@pytest.fixture
def repository(session: Session) -> PipelineRepository:
    repository = SQLAlchemyPipelineRepository(session)
    assert isinstance(repository, PipelineRepository)
    return repository


@pytest.fixture
def pipeline() -> Pipeline:
    return build_pipeline("alpha", "Alpha")


@pytest.fixture
def second_pipeline() -> Pipeline:
    return build_pipeline("beta", "Beta")


@pytest.fixture
def missing_pipeline_id() -> str:
    return "missing"


class TestSQLAlchemyPipelineRepository(PipelineRepositoryContract):
    pass

