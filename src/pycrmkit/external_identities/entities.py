"""External identifiers owned by CRM entities."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.exceptions import ValidationError

_SYSTEM_SEPARATORS = re.compile(r"[\s-]+")
_SYSTEM_PATTERN = re.compile(r"^[a-z][a-z0-9_.]{0,127}$")


class ExternalIdentityId(UUIDId):
    """Strongly typed identifier for one external identity mapping."""


def normalize_external_system(value: str) -> str:
    """Normalize an integration/system code into a stable comparison key."""

    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    code = _SYSTEM_SEPARATORS.sub("_", normalized)
    if not _SYSTEM_PATTERN.fullmatch(code):
        raise ValidationError(
            "external identity system must be a stable lowercase identifier",
            code="external_identity.system.invalid",
            context={"system": value},
        )
    return code


def normalize_external_id(value: str) -> str:
    """Normalize surrounding Unicode/whitespace without changing identifier case."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise ValidationError(
            "external identity external_id cannot be empty",
            code="external_identity.external_id.empty",
        )
    if len(normalized) > 512:
        raise ValidationError(
            "external identity external_id cannot exceed 512 characters",
            code="external_identity.external_id.too_long",
        )
    return normalized


@dataclass(eq=False, slots=True)
class ExternalIdentity(TimestampedEntity[ExternalIdentityId]):
    """Mapping from one external-system record to one PyCRMKit entity."""

    system: str
    external_id: str
    entity_type: str
    entity_id: UUIDId
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.system = normalize_external_system(self.system)
        self.external_id = normalize_external_id(self.external_id)
        self.entity_type = normalize_entity_kind(self.entity_type)
        if not isinstance(self.entity_id, UUIDId):
            raise ValidationError(
                "external identity entity_id must be a UUID-backed PyCRMKit identifier",
                code="external_identity.entity_id.invalid",
            )
        self.metadata = dict(self.metadata)

    @property
    def entity(self) -> EntityReference:
        """Return the mapped entity as a framework-neutral reference."""

        return EntityReference(self.entity_type, self.entity_id)


def same_entity(identity: ExternalIdentity, entity: EntityReference) -> bool:
    """Compare ownership without relying on a specific UUIDId subclass."""

    return (
        identity.entity_type == entity.kind
        and str(identity.entity_id) == str(entity.id)
    )


__all__ = [
    "ExternalIdentity",
    "ExternalIdentityId",
    "normalize_external_id",
    "normalize_external_system",
    "same_entity",
]
