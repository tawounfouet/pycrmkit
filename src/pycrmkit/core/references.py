"""Generic typed references to CRM entities without loading domain aggregates."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from pycrmkit.core.ids import UUIDId
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError

_KIND_SEPARATORS = re.compile(r"[\s-]+")
_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def normalize_entity_kind(value: str) -> str:
    """Normalize an entity-kind code used by cross-domain references."""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    code = _KIND_SEPARATORS.sub("_", normalized)
    if not _KIND_PATTERN.fullmatch(code):
        raise ValidationError(
            "entity kind must be a stable lowercase identifier",
            code="entity_reference.kind.invalid",
            context={"kind": value},
        )
    return code


@dataclass(frozen=True, slots=True)
class EntityReference(ValueObject):
    """Reference an entity by stable kind and UUID-backed domain identifier."""

    kind: str
    id: UUIDId

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", normalize_entity_kind(self.kind))
        if not isinstance(self.id, UUIDId):
            raise ValidationError(
                "entity references require a UUID-backed PyCRMKit identifier",
                code="entity_reference.id.invalid",
            )

    def __str__(self) -> str:
        return f"{self.kind}:{self.id}"
