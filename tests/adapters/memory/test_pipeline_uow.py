from decimal import Decimal

from pycrmkit.pipelines import Pipeline, Stage
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork


def pipeline(pipeline_id: str = "sales") -> Pipeline:
    return Pipeline(
        id=pipeline_id,
        name="Sales",
        stages=(Stage("new", "New", 0, Decimal("0.1")),),
    )


def test_pipeline_uow_commit_persists() -> None:
    store = MemoryStore()
    with MemoryUnitOfWork(store) as uow:
        uow.pipelines.save(pipeline())
        uow.commit()
    with MemoryUnitOfWork(store) as uow:
        assert uow.pipelines.get("sales").name == "Sales"


def test_pipeline_uow_exit_without_commit_rolls_back() -> None:
    store = MemoryStore()
    with MemoryUnitOfWork(store) as uow:
        uow.pipelines.save(pipeline())
    with MemoryUnitOfWork(store) as uow:
        assert uow.pipelines.find("sales") is None
