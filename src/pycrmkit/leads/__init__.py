"""Public Lead-domain API."""

from pycrmkit.leads.conversion import LeadConversionResult, LeadConversionService
from pycrmkit.leads.entities import Lead, LeadId, LeadStatus
from pycrmkit.leads.queries import LeadQuery
from pycrmkit.leads.repository import LeadRepository
from pycrmkit.leads.services import LeadService

__all__ = [
    "Lead",
    "LeadConversionResult",
    "LeadConversionService",
    "LeadId",
    "LeadQuery",
    "LeadRepository",
    "LeadService",
    "LeadStatus",
]
