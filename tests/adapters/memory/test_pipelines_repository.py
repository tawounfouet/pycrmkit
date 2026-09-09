from decimal import Decimal

import pytest

from pycrmkit.pipelines import Pipeline, PipelineRepository, Stage, StageTransition
from pycrmkit.storage.memory import MemoryPipelineRepository

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
def repository() -> PipelineRepository:
    repository = MemoryPipelineRepository()
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


class TestMemoryPipelineRepository(PipelineRepositoryContract):
    pass


def test_repository_returns_copy_isolated_pipeline(pipeline: Pipeline) -> None:
    repository = MemoryPipelineRepository()
    repository.save(pipeline)
    loaded = repository.get(pipeline.id)
    assert loaded == pipeline
    assert loaded is not pipeline
