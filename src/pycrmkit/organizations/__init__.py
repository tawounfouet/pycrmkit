"""Public Organization-domain API."""

from pycrmkit.organizations.dto import UNSET, OrganizationUpdate, UnsetType
from pycrmkit.organizations.entities import Organization, OrganizationId, OrganizationStatus
from pycrmkit.organizations.queries import OrganizationQuery
from pycrmkit.organizations.repository import OrganizationRepository
from pycrmkit.organizations.services import OrganizationService
from pycrmkit.organizations.value_objects import (
    OrganizationAddress,
    OrganizationDomain,
    normalize_domain,
)

__all__ = [
    "UNSET",
    "Organization",
    "OrganizationAddress",
    "OrganizationDomain",
    "OrganizationId",
    "OrganizationQuery",
    "OrganizationRepository",
    "OrganizationService",
    "OrganizationStatus",
    "OrganizationUpdate",
    "UnsetType",
    "normalize_domain",
]
