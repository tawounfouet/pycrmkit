"""In-memory Campaign attribution and communication linkage repository."""

from __future__ import annotations

import unicodedata
from copy import deepcopy

from pycrmkit.campaigns import CampaignId
from pycrmkit.campaigns.linkage import (
    CampaignAttributionReference,
    CampaignCommunicationLink,
    normalize_campaign_external_ref,
)
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError
from pycrmkit.storage.memory._state import _MemoryState


def _source_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


class MemoryCampaignLinkageRepository:
    """Copy-isolated Campaign linkage repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def add_attribution(
        self,
        reference: CampaignAttributionReference,
    ) -> CampaignAttributionReference:
        key = (
            reference.campaign_id,
            reference.target,
            reference.source,
            reference.external_ref,
        )
        if key in self._state.campaign_attributions:
            raise DuplicateError(
                "Campaign attribution reference already exists",
                code="campaign.attribution.duplicate",
                context={
                    "campaign_id": str(reference.campaign_id),
                    "entity_kind": reference.target.kind,
                    "entity_id": str(reference.target.id),
                    "source": reference.source,
                    "external_ref": reference.external_ref,
                },
            )
        self._state.campaign_attributions[key] = deepcopy(reference)
        return deepcopy(reference)

    def remove_attribution(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        source: str,
        external_ref: str | None,
    ) -> bool:
        key = (
            campaign_id,
            target,
            _source_key(source),
            normalize_campaign_external_ref(external_ref),
        )
        return self._state.campaign_attributions.pop(key, None) is not None

    def list_attributions(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignAttributionReference]:
        values = [
            reference
            for (stored_campaign_id, _, _, _), reference
            in self._state.campaign_attributions.items()
            if stored_campaign_id == campaign_id
        ]
        values.sort(
            key=lambda item: (
                item.recorded_at,
                item.source,
                item.target.kind,
                str(item.target.id),
                item.external_ref or "",
            )
        )
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def add_communication_link(
        self,
        link: CampaignCommunicationLink,
    ) -> CampaignCommunicationLink:
        key = (link.campaign_id, link.communication_id)
        if key in self._state.campaign_communication_links:
            raise DuplicateError(
                "Campaign communication link already exists",
                code="campaign.communication_link.duplicate",
                context={
                    "campaign_id": str(link.campaign_id),
                    "communication_id": str(link.communication_id),
                },
            )
        self._state.campaign_communication_links[key] = deepcopy(link)
        return deepcopy(link)

    def remove_communication_link(
        self,
        campaign_id: CampaignId,
        communication_id: CommunicationRecordId,
    ) -> bool:
        return (
            self._state.campaign_communication_links.pop(
                (campaign_id, communication_id),
                None,
            )
            is not None
        )

    def list_communication_links(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignCommunicationLink]:
        values = [
            link
            for (stored_campaign_id, _), link
            in self._state.campaign_communication_links.items()
            if stored_campaign_id == campaign_id
        ]
        values.sort(key=lambda item: (item.linked_at, str(item.communication_id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )


__all__ = ["MemoryCampaignLinkageRepository"]
