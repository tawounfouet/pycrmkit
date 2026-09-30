"""Campaign metadata domain."""

from pycrmkit.campaigns.dto import CampaignUpdate, UNSET, UnsetType
from pycrmkit.campaigns.entities import Campaign, CampaignId, normalize_campaign_key
from pycrmkit.campaigns.enums import CampaignStatus
from pycrmkit.campaigns.queries import CampaignQuery
from pycrmkit.campaigns.repository import CampaignRepository
from pycrmkit.campaigns.services import CampaignService
from pycrmkit.campaigns.unit_of_work import CampaignUnitOfWork

__all__ = [
    "Campaign",
    "CampaignId",
    "CampaignQuery",
    "CampaignRepository",
    "CampaignService",
    "CampaignStatus",
    "CampaignUnitOfWork",
    "CampaignUpdate",
    "UNSET",
    "UnsetType",
    "normalize_campaign_key",
]
