"""Relationship value objects and endpoint semantics."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from pycrmkit.contacts.entities import ContactId
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError
from pycrmkit.organizations.entities import OrganizationId

_WHITESPACE = re.compile(r"\s+")
_TYPE_SEPARATORS = re.compile(r"[\s_]+")


def normalize_relationship_type(value: str) -> str:
    """Normalize a relationship type into a stable lowercase semantic code."""
    normalized = _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())
    code = _TYPE_SEPARATORS.sub("-", normalized).casefold()
    if not code:
        raise ValidationError(
            "relationship type cannot be empty",
            code="relationship.type.required",
        )
    if len(code) > 80:
        raise ValidationError(
            "relationship type cannot exceed 80 characters",
            code="relationship.type.too_long",
        )
    return code


class RelationshipEntityKind(StrEnum):
    """Entity kinds that can participate in V0.1 CRM relationships."""

    CONTACT = "contact"
    ORGANIZATION = "organization"


RelationshipEntityId = ContactId | OrganizationId


@dataclass(frozen=True, slots=True)
class RelationshipEndpoint(ValueObject):
    """Typed reference to a relationship participant without loading the entity."""

    kind: RelationshipEntityKind
    id: RelationshipEntityId

    def __post_init__(self) -> None:
        if self.kind is RelationshipEntityKind.CONTACT and not isinstance(self.id, ContactId):
            raise ValidationError(
                "contact endpoints require ContactId",
                code="relationship.endpoint.contact_id_required",
            )
        if self.kind is RelationshipEntityKind.ORGANIZATION and not isinstance(
            self.id, OrganizationId
        ):
            raise ValidationError(
                "organization endpoints require OrganizationId",
                code="relationship.endpoint.organization_id_required",
            )

    @classmethod
    def contact(cls, contact_id: ContactId) -> RelationshipEndpoint:
        """Create a Contact endpoint."""
        return cls(RelationshipEntityKind.CONTACT, contact_id)

    @classmethod
    def organization(cls, organization_id: OrganizationId) -> RelationshipEndpoint:
        """Create an Organization endpoint."""
        return cls(RelationshipEntityKind.ORGANIZATION, organization_id)


@dataclass(frozen=True, slots=True)
class RelationshipType(ValueObject):
    """Open-ended relationship classification represented by a stable code."""

    code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalize_relationship_type(self.code))

    def __str__(self) -> str:
        return self.code
