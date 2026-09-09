"""Persistence contract for Pipeline definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.pipelines.entities import Pipeline


@runtime_checkable
class PipelineRepository(Protocol):
    """Backend-neutral repository for immutable pipeline definitions."""

    def get(self, pipeline_id: str) -> Pipeline:
        """Return a pipeline or raise NotFoundError."""

    def find(self, pipeline_id: str) -> Pipeline | None:
        """Return a pipeline or None."""

    def save(self, pipeline: Pipeline) -> None:
        """Persist one pipeline definition inside the outer transaction."""

    def list(self, page: OffsetPageRequest) -> Page[Pipeline]:
        """List definitions in deterministic id order."""
