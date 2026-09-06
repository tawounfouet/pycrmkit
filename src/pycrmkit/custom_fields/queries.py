"""Backend-independent Custom Field definition queries."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.custom_fields.value_objects import CustomFieldType


@dataclass(frozen=True, slots=True)
class CustomFieldDefinitionQuery:
    """Portable filters over latest custom-field definition revisions."""

    key: str | None = None
    field_type: CustomFieldType | None = None
    entity_kind: str | None = None
    include_inactive: bool = False
