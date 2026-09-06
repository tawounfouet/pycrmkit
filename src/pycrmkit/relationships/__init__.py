"""Public Relationship-domain API."""

from pycrmkit.relationships.dto import UNSET, RelationshipUpdate, UnsetType
from pycrmkit.relationships.entities import Relationship, RelationshipId
from pycrmkit.relationships.queries import RelationshipQuery
from pycrmkit.relationships.repository import RelationshipRepository
from pycrmkit.relationships.services import RelationshipService
from pycrmkit.relationships.value_objects import (
    RelationshipEndpoint,
    RelationshipEntityKind,
    RelationshipType,
    normalize_relationship_type,
)

__all__ = [
    "UNSET",
    "Relationship",
    "RelationshipEndpoint",
    "RelationshipEntityKind",
    "RelationshipId",
    "RelationshipQuery",
    "RelationshipRepository",
    "RelationshipService",
    "RelationshipType",
    "RelationshipUpdate",
    "UnsetType",
    "normalize_relationship_type",
]
