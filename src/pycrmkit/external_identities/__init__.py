"""External-system identity mappings for CRM entities."""

from pycrmkit.external_identities.entities import (
    ExternalIdentity,
    ExternalIdentityId,
    normalize_external_id,
    normalize_external_system,
    same_entity,
)
from pycrmkit.external_identities.repository import ExternalIdentityRepository
from pycrmkit.external_identities.services import ExternalIdentityService

__all__ = [
    "ExternalIdentity",
    "ExternalIdentityId",
    "ExternalIdentityRepository",
    "ExternalIdentityService",
    "normalize_external_id",
    "normalize_external_system",
    "same_entity",
]
