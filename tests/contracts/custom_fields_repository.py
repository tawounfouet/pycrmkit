"""Reusable CustomFieldRepository conformance assertions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields.entities import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldValue,
    CustomFieldValueId,
)
from pycrmkit.custom_fields.queries import CustomFieldDefinitionQuery
from pycrmkit.custom_fields.repository import CustomFieldRepository
from pycrmkit.custom_fields.value_objects import CustomFieldType
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def make_definition(number: int, key: str, version: int = 1) -> CustomFieldDefinition:
    return CustomFieldDefinition(
        id=CustomFieldDefinitionId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        key=key,
        label=key.replace("_", " ").title(),
        field_type=CustomFieldType.STRING,
        schema_version=version,
        applies_to=("contact",),
    )


def assert_custom_field_repository_contract(repository: CustomFieldRepository) -> None:
    alpha = make_definition(1, "alpha")
    beta = make_definition(2, "beta")
    repository.save_definition(beta)
    repository.save_definition(alpha)

    assert repository.get_definition(alpha.id) == alpha
    assert repository.find_definition_by_key("alpha") == alpha
    with pytest.raises(NotFoundError):
        repository.get_definition(CustomFieldDefinitionId(UUID(int=999)))

    with pytest.raises(DuplicateError):
        repository.save_definition(make_definition(3, "alpha"))

    alpha_v2 = make_definition(1, "alpha", version=2)
    repository.save_definition(alpha_v2)
    assert repository.get_definition(alpha.id).schema_version == 2
    assert repository.get_definition(alpha.id, 1).schema_version == 1
    assert [item.schema_version for item in repository.list_definition_versions(alpha.id)] == [1, 2]

    with pytest.raises(ConflictError):
        repository.save_definition(make_definition(1, "alpha", version=4))

    page = repository.search_definitions(
        CustomFieldDefinitionQuery(),
        OffsetPageRequest(limit=1),
    )
    assert page.total == 2
    assert page.items[0].key == "alpha"

    entity = EntityReference("contact", EntityId(UUID(int=100)))
    value = CustomFieldValue(
        id=CustomFieldValueId(UUID(int=20)),
        created_at=NOW,
        updated_at=NOW,
        definition_id=alpha.id,
        entity=entity,
        schema_version=2,
        value="hello",
    )
    repository.save_value(value)
    assert repository.get_value(alpha.id, entity) == value
    assert repository.find_value(alpha.id, entity) == value
    assert repository.list_values(entity, OffsetPageRequest()).items == (value,)
    assert repository.remove_value(alpha.id, entity) is True
    assert repository.remove_value(alpha.id, entity) is False
    with pytest.raises(NotFoundError):
        repository.get_value(alpha.id, entity)
