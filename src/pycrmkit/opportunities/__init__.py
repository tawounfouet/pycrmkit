"""Sales opportunity domain."""

from pycrmkit.opportunities.entities import Opportunity, OpportunityId, OpportunityStatus
from pycrmkit.opportunities.queries import OpportunityQuery
from pycrmkit.opportunities.repository import OpportunityRepository
from pycrmkit.opportunities.services import OpportunityService

__all__ = [
    "Opportunity",
    "OpportunityId",
    "OpportunityQuery",
    "OpportunityRepository",
    "OpportunityService",
    "OpportunityStatus",
]
