"""SQLAlchemy TaskRepository implementation."""

from __future__ import annotations

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.sqlalchemy.mappers import task_from_model, task_to_model
from pycrmkit.storage.sqlalchemy.models.task import TaskModel, TaskReferenceModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models
from pycrmkit.tasks import Task, TaskId, TaskOrdering, TaskQuery, TaskStatus


class SQLAlchemyTaskRepository:
    """SQLAlchemy adapter preserving deterministic due-date ordering."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, task_id: TaskId) -> Task:
        task = self.find(task_id)
        if task is None:
            raise NotFoundError(
                "task not found",
                code="task.not_found",
                context={"task_id": str(task_id)},
            )
        return task

    def find(self, task_id: TaskId) -> Task | None:
        model = self.session.get(TaskModel, str(task_id))
        return None if model is None else self._hydrate(model)

    def save(self, task: Task) -> None:
        model = self.session.get(TaskModel, str(task.id))
        target = task_to_model(task, model)
        if model is None:
            self.session.add(target)
        key = str(task.id)
        self.session.execute(
            delete(TaskReferenceModel).where(
                TaskReferenceModel.task_id == key
            )
        )
        self.session.add_all(
            [
                TaskReferenceModel(
                    task_id=key,
                    position=position,
                    entity_kind=reference.kind,
                    entity_id=str(reference.id),
                )
                for position, reference in enumerate(task.references)
            ]
        )

    def list(
        self,
        query: TaskQuery,
        page: OffsetPageRequest,
    ) -> Page[Task]:
        statement = select(TaskModel)
        if query.status is not None:
            statement = statement.where(
                TaskModel.status == query.status.value
            )
        if query.unresolved_only:
            statement = statement.where(
                TaskModel.status.in_(
                    [TaskStatus.OPEN.value, TaskStatus.IN_PROGRESS.value]
                )
            )
        if query.type is not None:
            statement = statement.where(TaskModel.task_type == query.type.value)
        if query.priority is not None:
            statement = statement.where(
                TaskModel.priority == int(query.priority)
            )
        if query.owner_id is not None:
            statement = statement.where(
                TaskModel.owner_id == query.owner_id
            )
        if query.assignee_id is not None:
            statement = statement.where(
                TaskModel.assignee_id == query.assignee_id
            )
        if query.reference is not None:
            statement = statement.where(
                exists(
                    select(TaskReferenceModel.id).where(
                        TaskReferenceModel.task_id == TaskModel.id,
                        TaskReferenceModel.entity_kind
                        == query.reference.kind,
                        TaskReferenceModel.entity_id
                        == str(query.reference.id),
                    )
                )
            )
        if query.source is not None:
            statement = statement.where(
                func.lower(TaskModel.source) == query.source
            )
        if query.external_id is not None:
            statement = statement.where(
                TaskModel.external_id == query.external_id
            )
        if query.due_from is not None:
            statement = statement.where(
                TaskModel.due_at.is_not(None),
                TaskModel.due_at >= query.due_from,
            )
        if query.due_until is not None:
            statement = statement.where(
                TaskModel.due_at.is_not(None),
                TaskModel.due_at < query.due_until,
            )
        if query.overdue_at is not None:
            statement = statement.where(
                TaskModel.status.in_(
                    [
                        TaskStatus.OPEN.value,
                        TaskStatus.IN_PROGRESS.value,
                    ]
                ),
                TaskModel.due_at.is_not(None),
                TaskModel.due_at < query.overdue_at,
            )
        if query.unscheduled_only:
            statement = statement.where(TaskModel.due_at.is_(None))

        if query.ordering is TaskOrdering.DUE_PRIORITY_CREATED:
            statement = statement.order_by(
                TaskModel.due_at.asc(),
                TaskModel.priority.desc(),
                TaskModel.created_at.asc(),
                TaskModel.id.asc(),
            )
        elif query.ordering is TaskOrdering.DUE_PRIORITY:
            statement = statement.order_by(
                TaskModel.due_at.asc(),
                TaskModel.priority.desc(),
                TaskModel.id.asc(),
            )
        elif query.ordering is TaskOrdering.PRIORITY_CREATED:
            statement = statement.order_by(
                TaskModel.priority.desc(),
                TaskModel.created_at.asc(),
                TaskModel.id.asc(),
            )
        else:
            statement = statement.order_by(
                TaskModel.due_at.is_(None).asc(),
                TaskModel.due_at.asc(),
                TaskModel.created_at.desc(),
                TaskModel.id.asc(),
            )
        return page_models(
            self.session,
            statement,
            page,
            self._hydrate,
        )

    def _hydrate(self, model: TaskModel) -> Task:
        references = list(
            self.session.scalars(
                select(TaskReferenceModel)
                .where(TaskReferenceModel.task_id == model.id)
                .order_by(
                    TaskReferenceModel.position.asc(),
                    TaskReferenceModel.id.asc(),
                )
            )
        )
        return task_from_model(model, references)
