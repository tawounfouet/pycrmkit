"""Run Custom Field repository contracts against the official Memory adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pycrmkit.custom_fields.entities import CustomFieldDefinition, CustomFieldDefinitionId
from pycrmkit.custom_fields.value_objects import CustomFieldType
from pycrmkit.storage.memory import MemoryCustomFieldRepository
from ...contracts.custom_fields_repository import assert_custom_field_repository_contract

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def test_memory_custom_field_repository_passes_contract() -> None:
    assert_custom_field_repository_contract(MemoryCustomFieldRepository())


def test_custom_field_repository_isolates_definition_mutations() -> None:
    repository = MemoryCustomFieldRepository()
    definition = CustomFieldDefinition(
        id=CustomFieldDefinitionId(UUID(int=1)),
        created_at=NOW,
        updated_at=NOW,
        key="account_tier",
        label="Account Tier",
        field_type=CustomFieldType.STRING,
        schema_version=1,
        applies_to=("contact",),
        metadata={"source": "test"},
    )
    repository.save_definition(definition)
    definition.metadata["source"] = "changed"
    assert repository.get_definition(definition.id).metadata == {"source": "test"}

    loaded = repository.get_definition(definition.id)
    loaded.metadata["source"] = "changed-again"
    assert repository.get_definition(definition.id).metadata == {"source": "test"}
