"""Small JSON-contract helpers shared by public event and audit records."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from types import MappingProxyType

from pycrmkit.exceptions import ValidationError


def freeze_json_value(value: object) -> object:
    """Validate and recursively freeze a JSON-compatible value.

    JSON objects become read-only mappings and arrays become tuples. This keeps
    public event/audit records deeply immutable without depending on a serializer.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValidationError(
                "JSON numbers must be finite",
                code="json.value.non_finite",
            )
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError(
                    "JSON object keys must be strings",
                    code="json.key.invalid",
                )
            frozen[key] = freeze_json_value(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json_value(item) for item in value)
    raise ValidationError(
        "value is not JSON-compatible",
        code="json.value.invalid",
        context={"type": type(value).__name__},
    )


def freeze_json_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Validate and deeply freeze a JSON object mapping."""

    frozen = freeze_json_value(value)
    assert isinstance(frozen, Mapping)
    return frozen


def thaw_json_value(value: object) -> object:
    """Return a mutable JSON-compatible representation of a frozen value."""

    if isinstance(value, Mapping):
        return {str(key): thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json_value(item) for item in value]
    return value


def thaw_json_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """Return a mutable JSON object representation."""

    thawed = thaw_json_value(value)
    assert isinstance(thawed, dict)
    return thawed
