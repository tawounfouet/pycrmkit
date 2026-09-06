"""Persistence contract for versioned custom fields and current values."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields.entities import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldValue,
)
from pycrmkit.custom_fields.queries import CustomFieldDefinitionQuery


@runtime_checkable
class CustomFieldRepository(Protocol):
    """Observable persistence semantics shared by all Custom Field adapters."""

    def get_definition(
        self,
        definition_id: CustomFieldDefinitionId,
        version: int | None = None,
    ) -> CustomFieldDefinition:
        """Return the latest or requested definition revision, else NotFoundError."""

    def find_definition_by_key(self, key: str) -> CustomFieldDefinition | None:
        """Return the latest revision for a normalized key, or None."""

    def save_definition(self, definition: CustomFieldDefinition) -> None:
        """Append one definition revision, enforcing key and version invariants."""

    def list_definition_versions(
        self,
        definition_id: CustomFieldDefinitionId,
    ) -> tuple[CustomFieldDefinition, ...]:
        """Return all revisions ordered by schema_version ascending."""

    def search_definitions(
        self,
        query: CustomFieldDefinitionQuery,
        page: OffsetPageRequest,
    ) -> Page[CustomFieldDefinition]:
        """Search latest revisions only with deterministic ordering."""

    def get_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> CustomFieldValue:
        """Return the current value for a definition/entity pair or NotFoundError."""

    def find_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> CustomFieldValue | None:
        """Return the current value or None."""

    def save_value(self, value: CustomFieldValue) -> None:
        """Persist the current value for a definition/entity pair."""

    def remove_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> bool:
        """Remove the current value, returning whether one existed."""

    def list_values(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[CustomFieldValue]:
        """List current values for one entity with deterministic ordering."""
