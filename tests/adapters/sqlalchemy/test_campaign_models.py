"""Structural qualification for Campaign SQLAlchemy persistence models."""

from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, Table, UniqueConstraint

from pycrmkit.storage.sqlalchemy.base import Base
from pycrmkit.storage.sqlalchemy.models.campaign import (
    CampaignAttributionModel,
    CampaignCommunicationLinkModel,
    CampaignMemberModel,
    CampaignModel,
    CampaignSegmentMemberModel,
    CampaignSegmentSourceModel,
)


def _index_columns(table: Table) -> set[tuple[str, ...]]:
    return {tuple(column.name for column in index.columns) for index in table.indexes}


def _unique_constraints(table: Table) -> dict[str | None, tuple[str, ...]]:
    return {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_keys(
    table: Table,
) -> set[tuple[tuple[str, ...], tuple[str, ...], str | None]]:
    return {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }


def test_campaign_models_register_all_six_tables() -> None:
    expected = {
        "pycrmkit_campaigns",
        "pycrmkit_campaign_members",
        "pycrmkit_campaign_segment_sources",
        "pycrmkit_campaign_segment_members",
        "pycrmkit_campaign_attributions",
        "pycrmkit_campaign_communication_links",
    }

    assert expected <= set(Base.metadata.tables)
    assert CampaignModel.__tablename__ == "pycrmkit_campaigns"
    assert CampaignMemberModel.__tablename__ == "pycrmkit_campaign_members"
    assert CampaignSegmentSourceModel.__tablename__ == "pycrmkit_campaign_segment_sources"
    assert CampaignSegmentMemberModel.__tablename__ == "pycrmkit_campaign_segment_members"
    assert CampaignAttributionModel.__tablename__ == "pycrmkit_campaign_attributions"
    assert CampaignCommunicationLinkModel.__tablename__ == "pycrmkit_campaign_communication_links"


def test_campaign_table_has_required_search_indexes() -> None:
    indexes = _index_columns(CampaignModel.__table__)

    assert {
        ("status",),
        ("owner_id",),
        ("archived_at",),
        ("created_at",),
    } <= indexes


def test_campaign_member_constraints_match_memory_identity() -> None:
    table = CampaignMemberModel.__table__

    assert _unique_constraints(table)["uq_pycrmkit_campaign_members_target"] == (
        "campaign_id",
        "entity_kind",
        "entity_id",
    )
    assert ("entity_kind", "entity_id") in _index_columns(table)
    assert (
        ("campaign_id",),
        ("pycrmkit_campaigns.id",),
        "CASCADE",
    ) in _foreign_keys(table)


def test_campaign_segment_source_and_capture_use_ownership_keys() -> None:
    source = CampaignSegmentSourceModel.__table__
    captured = CampaignSegmentMemberModel.__table__

    assert tuple(column.name for column in source.primary_key.columns) == (
        "campaign_id",
        "segment_id",
    )
    assert ("segment_id",) in _index_columns(source)
    assert ("campaign_id", "attached_at") in _index_columns(source)
    assert (
        ("campaign_id",),
        ("pycrmkit_campaigns.id",),
        "CASCADE",
    ) in _foreign_keys(source)

    assert _unique_constraints(captured)["uq_pycrmkit_campaign_segment_members_target"] == (
        "campaign_id",
        "segment_id",
        "entity_kind",
        "entity_id",
    )
    assert ("campaign_id", "segment_id") in _index_columns(captured)
    assert ("entity_kind", "entity_id") in _index_columns(captured)
    assert (
        ("campaign_id", "segment_id"),
        (
            "pycrmkit_campaign_segment_sources.campaign_id",
            "pycrmkit_campaign_segment_sources.segment_id",
        ),
        "CASCADE",
    ) in _foreign_keys(captured)


def test_attribution_uniqueness_preserves_none_normalization_strategy() -> None:
    table = CampaignAttributionModel.__table__

    assert not table.c.external_ref.nullable
    assert table.c.external_ref.default is not None
    assert table.c.external_ref.default.arg == ""
    assert _unique_constraints(table)["uq_pycrmkit_campaign_attributions_reference"] == (
        "campaign_id",
        "target_kind",
        "target_id",
        "source",
        "external_ref",
    )
    assert ("target_kind", "target_id") in _index_columns(table)
    assert ("campaign_id", "recorded_at") in _index_columns(table)
    assert ("source",) in _index_columns(table)


def test_communication_link_has_only_campaign_ownership_fk() -> None:
    table = CampaignCommunicationLinkModel.__table__

    assert _unique_constraints(table)["uq_pycrmkit_campaign_communication_links_record"] == (
        "campaign_id",
        "communication_id",
    )
    assert ("communication_id",) in _index_columns(table)
    assert ("campaign_id", "linked_at") in _index_columns(table)
    assert _foreign_keys(table) == {
        (
            ("campaign_id",),
            ("pycrmkit_campaigns.id",),
            "CASCADE",
        )
    }
