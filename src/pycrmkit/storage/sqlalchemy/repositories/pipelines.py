"""SQLAlchemy PipelineRepository implementation."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.pipelines import Pipeline, normalize_pipeline_id
from pycrmkit.storage.sqlalchemy.mappers import pipeline_from_models
from pycrmkit.storage.sqlalchemy.models.pipeline import (
    PipelineModel,
    PipelineStageModel,
    PipelineTransitionModel,
)


class SQLAlchemyPipelineRepository:
    """SQLAlchemy adapter for immutable commercial pipeline definitions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, pipeline_id: str) -> Pipeline:
        key = normalize_pipeline_id(pipeline_id)
        pipeline = self.find(key)
        if pipeline is None:
            raise NotFoundError(
                "pipeline not found",
                code="pipeline.not_found",
                context={"pipeline_id": key},
            )
        return pipeline

    def find(self, pipeline_id: str) -> Pipeline | None:
        key = normalize_pipeline_id(pipeline_id)
        model = self.session.get(PipelineModel, key)
        return None if model is None else self._hydrate(model)

    def save(self, pipeline: Pipeline) -> None:
        model = self.session.get(PipelineModel, pipeline.id)
        if model is None:
            model = PipelineModel(
                id=pipeline.id,
                name=pipeline.name,
            )
            self.session.add(model)
        else:
            model.name = pipeline.name
        self.session.execute(
            delete(PipelineStageModel).where(
                PipelineStageModel.pipeline_id == pipeline.id
            )
        )
        self.session.execute(
            delete(PipelineTransitionModel).where(
                PipelineTransitionModel.pipeline_id == pipeline.id
            )
        )
        self.session.add_all(
            [
                PipelineStageModel(
                    pipeline_id=pipeline.id,
                    id=stage.id,
                    name=stage.name,
                    position=stage.position,
                    default_probability=stage.default_probability,
                    terminal=stage.terminal,
                    outcome=(
                        stage.outcome.value
                        if stage.outcome is not None
                        else None
                    ),
                )
                for stage in pipeline.stages
            ]
        )
        self.session.add_all(
            [
                PipelineTransitionModel(
                    pipeline_id=pipeline.id,
                    from_stage=transition.from_stage,
                    to_stage=transition.to_stage,
                )
                for transition in pipeline.transitions
            ]
        )

    def list(self, page: OffsetPageRequest) -> Page[Pipeline]:
        statement = select(PipelineModel).order_by(
            PipelineModel.id.asc()
        )
        total = int(
            self.session.scalar(
                select(func.count()).select_from(PipelineModel)
            )
            or 0
        )
        models = self.session.scalars(
            statement.offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=tuple(
                self._hydrate(model)
                for model in models
            ),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def _hydrate(self, model: PipelineModel) -> Pipeline:
        stages = list(
            self.session.scalars(
                select(PipelineStageModel)
                .where(
                    PipelineStageModel.pipeline_id == model.id
                )
                .order_by(
                    PipelineStageModel.position.asc(),
                    PipelineStageModel.id.asc(),
                )
            )
        )
        transitions = list(
            self.session.scalars(
                select(PipelineTransitionModel)
                .where(
                    PipelineTransitionModel.pipeline_id == model.id
                )
                .order_by(
                    PipelineTransitionModel.from_stage.asc(),
                    PipelineTransitionModel.to_stage.asc(),
                )
            )
        )
        return pipeline_from_models(
            model,
            stages,
            transitions,
        )
