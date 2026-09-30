"""Campaign metadata and audience domain."""

from pycrmkit.campaigns.audience import CampaignMember, CampaignSegmentSource
from pycrmkit.campaigns.audience_repository import CampaignAudienceRepository
from pycrmkit.campaigns.audience_services import CampaignAudienceService
from pycrmkit.campaigns.audience_unit_of_work import CampaignAudienceUnitOfWork
from pycrmkit.campaigns.dto import UNSET, CampaignUpdate, UnsetType
from pycrmkit.campaigns.entities import Campaign, CampaignId, normalize_campaign_key
from pycrmkit.campaigns.enums import CampaignStatus
from pycrmkit.campaigns.queries import CampaignQuery
from pycrmkit.campaigns.repository import CampaignRepository
from pycrmkit.campaigns.services import CampaignService
from pycrmkit.campaigns.unit_of_work import CampaignUnitOfWork

__all__ = [
    "Campaign",
    "CampaignAudienceRepository",
    "CampaignAudienceService",
    "CampaignAudienceUnitOfWork",
    "CampaignId",
    "CampaignMember",
    "CampaignQuery",
    "CampaignRepository",
    "CampaignSegmentSource",
    "CampaignService",
    "CampaignStatus",
    "CampaignUnitOfWork",
    "CampaignUpdate",
    "UNSET",
    "UnsetType",
    "normalize_campaign_key",
]
