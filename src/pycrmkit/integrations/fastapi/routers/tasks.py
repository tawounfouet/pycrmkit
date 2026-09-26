"""FastAPI router for the public Tasks facade."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from pycrmkit import CRM
from pycrmkit.integrations.fastapi.dependencies import CRMDependency
from pycrmkit.integrations.fastapi.errors import (
    CREATE_ERROR_RESPONSES,
    LIST_ERROR_RESPONSES,
    MUTATION_ERROR_RESPONSES,
    READ_ERROR_RESPONSES,
)
from pycrmkit.integrations.fastapi.pagination import (
    PageResponse,
    PaginationParams,
    pagination_params,
)
from pycrmkit.integrations.fastapi.schemas import (
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
)
from pycrmkit.tasks import TaskId


def create_tasks_router(dependency: CRMDependency) -> APIRouter:
    """Build the Tasks router against one request-scoped CRM dependency."""

    router = APIRouter(prefix="/tasks", tags=["tasks"])

    @router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, responses=CREATE_ERROR_RESPONSES)
    def create_task(
        request: TaskCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> TaskResponse:
        task = crm.tasks.create(**request.to_domain_kwargs())
        return TaskResponse.from_domain(task)

    @router.get("", response_model=PageResponse[TaskResponse], responses=LIST_ERROR_RESPONSES)
    def list_tasks(
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[TaskResponse]:
        result = crm.tasks.list(page=page.to_domain())
        return PageResponse[TaskResponse].from_page(result, TaskResponse.from_domain)

    @router.get("/{task_id}", response_model=TaskResponse, responses=READ_ERROR_RESPONSES)
    def get_task(
        task_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> TaskResponse:
        task = crm.tasks.get(TaskId(task_id))
        return TaskResponse.from_domain(task)

    @router.patch("/{task_id}", response_model=TaskResponse, responses=MUTATION_ERROR_RESPONSES)
    def update_task(
        task_id: UUID,
        request: TaskUpdateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> TaskResponse:
        task = crm.tasks.update(TaskId(task_id), request.to_domain())
        return TaskResponse.from_domain(task)

    @router.post("/{task_id}/start", response_model=TaskResponse, responses=MUTATION_ERROR_RESPONSES)
    def start_task(
        task_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> TaskResponse:
        return TaskResponse.from_domain(crm.tasks.start(TaskId(task_id)))

    @router.post("/{task_id}/complete", response_model=TaskResponse, responses=MUTATION_ERROR_RESPONSES)
    def complete_task(
        task_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> TaskResponse:
        return TaskResponse.from_domain(crm.tasks.complete(TaskId(task_id)))

    @router.post("/{task_id}/cancel", response_model=TaskResponse, responses=MUTATION_ERROR_RESPONSES)
    def cancel_task(
        task_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> TaskResponse:
        return TaskResponse.from_domain(crm.tasks.cancel(TaskId(task_id)))

    @router.post("/{task_id}/reopen", response_model=TaskResponse, responses=MUTATION_ERROR_RESPONSES)
    def reopen_task(
        task_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> TaskResponse:
        return TaskResponse.from_domain(crm.tasks.reopen(TaskId(task_id)))

    return router


__all__ = ["create_tasks_router"]
