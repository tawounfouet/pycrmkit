from uuid import uuid4

import pytest

from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.exceptions import ValidationError


def test_entity_reference_normalizes_kind() -> None:
    reference = EntityReference("Sales Lead", EntityId(uuid4()))
    assert reference.kind == "sales_lead"
    assert str(reference).startswith("sales_lead:")


def test_entity_reference_rejects_invalid_kind() -> None:
    with pytest.raises(ValidationError) as exc_info:
        EntityReference("123", EntityId(uuid4()))
    assert exc_info.value.code == "entity_reference.kind.invalid"


def test_normalize_entity_kind_is_stable() -> None:
    assert normalize_entity_kind("  ORGANIZATION ") == "organization"
