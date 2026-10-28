"""Campaign metadata and audience domain."""

from pycrmkit.campaigns.audience import CampaignMember, CampaignSegmentSource
from pycrmkit.campaigns.audience_repository import CampaignAudienceRepository
from pycrmkit.campaigns.audience_services import CampaignAudienceService
from pycrmkit.campaigns.audience_unit_of_work import CampaignAudienceUnitOfWork
from pycrmkit.campaigns.data_operations import (
    MAX_CAMPAIGN_IMPORT_ROWS,
    CampaignDataOperationsAPI,
    CampaignMembershipDeduplicator,
    CampaignMembershipPersister,
    CampaignMembershipValidator,
    export_campaign_records,
    import_campaign_members,
    iter_campaign_audience_records,
    iter_campaign_direct_member_records,
    iter_campaign_segment_source_records,
)
from pycrmkit.campaigns.dto import UNSET, CampaignUpdate, UnsetType
from pycrmkit.campaigns.entities import Campaign, CampaignId, normalize_campaign_key
from pycrmkit.campaigns.enums import CampaignStatus
from pycrmkit.campaigns.linkage import (
    CampaignAttributionReference,
    CampaignCommunicationLink,
    normalize_campaign_external_ref,
)
from pycrmkit.campaigns.linkage_repository import CampaignLinkageRepository
from pycrmkit.campaigns.linkage_services import CampaignLinkageService
from pycrmkit.campaigns.linkage_unit_of_work import (
    CampaignAttributionUnitOfWork,
    CampaignLinkageUnitOfWork,
)
from pycrmkit.campaigns.queries import CampaignQuery
from pycrmkit.campaigns.repository import CampaignRepository
from pycrmkit.campaigns.services import CampaignService
from pycrmkit.campaigns.unit_of_work import CampaignUnitOfWork

__all__ = [
    "Campaign",
    "MAX_CAMPAIGN_IMPORT_ROWS",
    "CampaignDataOperationsAPI",
    "CampaignMembershipDeduplicator",
    "CampaignMembershipPersister",
    "CampaignMembershipValidator",
    "export_campaign_records",
    "import_campaign_members",
    "iter_campaign_audience_records",
    "iter_campaign_direct_member_records",
    "iter_campaign_segment_source_records",
    "CampaignAudienceRepository",
    "CampaignAudienceService",
    "CampaignAudienceUnitOfWork",
    "CampaignAttributionReference",
    "CampaignAttributionUnitOfWork",
    "CampaignCommunicationLink",
    "CampaignId",
    "CampaignLinkageRepository",
    "CampaignLinkageService",
    "CampaignLinkageUnitOfWork",
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
    "normalize_campaign_external_ref",
    "normalize_campaign_key",
]
