"""Domain <-> Django ORM Campaign codecs (no SQLAlchemy dependency)."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import overload

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignCommunicationLink,
    CampaignId,
    CampaignMember,
    CampaignSegmentSource,
    CampaignStatus,
)
from copy import deepcopy
from datetime import UTC, datetime
from typing import overload



from pycrmkit.communication import CommunicationRecordId
from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.integrations.django.models import (
    CampaignAttributionModel,
    CampaignCommunicationLinkModel,
    CampaignMemberModel,
    CampaignModel,
    CampaignSegmentMemberModel,
    CampaignSegmentSourceModel,
)
from pycrmkit.leads import LeadId
from pycrmkit.opportunities import OpportunityId
from pycrmkit.organizations import OrganizationId
from pycrmkit.segments import SegmentId




@overload
def aware(value: datetime) -> datetime: ...


@overload
def aware(value: None) -> None: ...


def aware(value: datetime | None) -> datetime | None:
    """Normalize DB timestamps including nullable and SQLite-naive variants."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def entity_reference(kind: str, identifier: str) -> EntityReference:
    """Hydrate one CRM reference while retaining its known typed ID."""
    by_kind: dict[str, type[UUIDId]] = {
        "contact": ContactId,
        "organization": OrganizationId,
        "lead": LeadId,
        "opportunity": OpportunityId,
    }
    id_type = by_kind.get(kind, UUIDId)
    return EntityReference(kind=kind, id=id_type.parse(identifier))


def campaign_to_model(
    campaign: Campaign,
    model: CampaignModel | None = None,
) -> CampaignModel:
    """Map Campaign domain state to its ORM representation."""

    target = model if model is not None else CampaignModel(
        id=str(campaign.id),
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )
    target.key = campaign.key
    target.name = campaign.name
    target.description = campaign.description
    target.status = campaign.status.value
    target.starts_at = campaign.starts_at
    target.ends_at = campaign.ends_at
    target.owner_id = str(campaign.owner_id) if campaign.owner_id is not None else None
    target.revision = campaign.revision
    target.metadata_json = deepcopy(dict(campaign.metadata))
    target.archived_at = campaign.archived_at
    target.created_at = campaign.created_at
    target.updated_at = campaign.updated_at
    return target


def campaign_from_model(model: CampaignModel) -> Campaign:
    """Hydrate a Campaign from ORM state."""

    return Campaign(
        id=CampaignId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        key=model.key,
        name=model.name,
        description=model.description,
        status=CampaignStatus(model.status),
        starts_at=aware(model.starts_at),
        ends_at=aware(model.ends_at),
        owner_id=EntityId.parse(model.owner_id) if model.owner_id is not None else None,
        revision=model.revision,
        metadata=deepcopy(dict(model.metadata_json or {})),
        archived_at=aware(model.archived_at),
    )


def campaign_member_to_model(member: CampaignMember) -> CampaignMemberModel:
    """Map one direct Campaign member to ORM state."""

    return CampaignMemberModel(
        campaign_id=str(member.campaign_id),
        entity_kind=member.entity.kind,
        entity_id=str(member.entity.id),
        added_at=member.added_at,
        source=member.source,
        actor_id=member.actor_id,
        metadata_json=deepcopy(dict(member.metadata)),
    )


def campaign_member_from_model(model: CampaignMemberModel) -> CampaignMember:
    """Hydrate one direct Campaign member."""

    return CampaignMember(
        campaign_id=CampaignId.parse(model.campaign_id),
        entity=entity_reference(model.entity_kind, model.entity_id),
        added_at=aware(model.added_at),
        source=model.source,
        actor_id=model.actor_id,
        metadata=deepcopy(dict(model.metadata_json or {})),
    )


def campaign_segment_source_to_model(
    source: CampaignSegmentSource,
    model: CampaignSegmentSourceModel | None = None,
) -> CampaignSegmentSourceModel:
    """Map one materialized Segment source to ORM state."""

    target = model if model is not None else CampaignSegmentSourceModel(
        campaign_id=str(source.campaign_id),
        segment_id=str(source.segment_id),
    )
    target.segment_revision = source.segment_revision
    target.entity_kind = source.entity_kind
    target.attached_at = source.attached_at
    target.captured_at = source.captured_at
    target.member_count = source.member_count
    target.actor_id = source.actor_id
    target.metadata_json = deepcopy(dict(source.metadata))
    return target


def campaign_segment_source_from_model(
    model: CampaignSegmentSourceModel,
) -> CampaignSegmentSource:
    """Hydrate one materialized Segment source."""

    return CampaignSegmentSource(
        campaign_id=CampaignId.parse(model.campaign_id),
        segment_id=SegmentId.parse(model.segment_id),
        segment_revision=model.segment_revision,
        entity_kind=model.entity_kind,
        attached_at=aware(model.attached_at),
        captured_at=aware(model.captured_at),
        member_count=model.member_count,
        actor_id=model.actor_id,
        metadata=deepcopy(dict(model.metadata_json or {})),
    )


def campaign_segment_member_to_model(
    source_id: int,
    member: EntityReference,
) -> CampaignSegmentMemberModel:
    """Map one captured Segment member reference to ORM state."""

    return CampaignSegmentMemberModel(
        source_id=source_id,
        entity_kind=member.kind,
        entity_id=str(member.id),
    )


def campaign_segment_member_from_model(
    model: CampaignSegmentMemberModel,
) -> EntityReference:
    """Hydrate one captured Segment member reference with its typed ID."""

    return entity_reference(model.entity_kind, model.entity_id)


def campaign_attribution_to_model(
    attribution: CampaignAttributionReference,
) -> CampaignAttributionModel:
    """Map a lightweight Campaign attribution reference to ORM state."""

    return CampaignAttributionModel(
        campaign_id=str(attribution.campaign_id),
        target_kind=attribution.target.kind,
        target_id=str(attribution.target.id),
        source=attribution.source,
        external_ref=_attribution_external_ref_to_db(attribution.external_ref),
        recorded_at=attribution.recorded_at,
        actor_id=attribution.actor_id,
        metadata_json=deepcopy(dict(attribution.metadata)),
    )


def campaign_attribution_from_model(
    model: CampaignAttributionModel,
) -> CampaignAttributionReference:
    """Hydrate a lightweight Campaign attribution reference."""

    return CampaignAttributionReference(
        campaign_id=CampaignId.parse(model.campaign_id),
        target=entity_reference(model.target_kind, model.target_id),
        source=model.source,
        recorded_at=aware(model.recorded_at),
        external_ref=_attribution_external_ref_from_db(model.external_ref),
        actor_id=model.actor_id,
        metadata=deepcopy(dict(model.metadata_json or {})),
    )


def campaign_communication_link_to_model(
    link: CampaignCommunicationLink,
) -> CampaignCommunicationLinkModel:
    """Map a Campaign communication link to ORM state."""

    return CampaignCommunicationLinkModel(
        campaign_id=str(link.campaign_id),
        communication_id=str(link.communication_id),
        linked_at=link.linked_at,
        role=link.role,
        actor_id=link.actor_id,
        metadata_json=deepcopy(dict(link.metadata)),
    )


def campaign_communication_link_from_model(
    model: CampaignCommunicationLinkModel,
) -> CampaignCommunicationLink:
    """Hydrate a Campaign communication link."""

    return CampaignCommunicationLink(
        campaign_id=CampaignId.parse(model.campaign_id),
        communication_id=CommunicationRecordId.parse(model.communication_id),
        linked_at=aware(model.linked_at),
        role=model.role,
        actor_id=model.actor_id,
        metadata=deepcopy(dict(model.metadata_json or {})),
    )


def _attribution_external_ref_to_db(value: str | None) -> str:
    return "" if value is None else value


def _attribution_external_ref_from_db(value: str) -> str | None:
    return None if value == "" else value


__all__ = [
    "campaign_attribution_from_model",
    "campaign_attribution_to_model",
    "campaign_communication_link_from_model",
    "campaign_communication_link_to_model",
    "campaign_from_model",
    "campaign_member_from_model",
    "campaign_member_to_model",
    "campaign_segment_member_from_model",
    "campaign_segment_member_to_model",
    "campaign_segment_source_from_model",
    "campaign_segment_source_to_model",
    "campaign_to_model",
]
