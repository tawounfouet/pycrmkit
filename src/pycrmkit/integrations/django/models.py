"""Django ORM persistence models for the PyCRMKit adapter.

These are persistence representations, not domain entities. Their schema is
managed by the adapter-specific Django migrations shipped with PyCRMKit.
"""

from __future__ import annotations

from django.db import models


class _TimestampedModel(models.Model):
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        abstract = True


class ContactModel(_TimestampedModel):
    id = models.CharField(max_length=36, primary_key=True)
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    display_name = models.CharField(max_length=511, null=True)
    status = models.CharField(max_length=32, db_index=True)
    owner_id = models.CharField(max_length=255, null=True, db_index=True)
    source = models.CharField(max_length=255, null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)
    archived_at = models.DateTimeField(null=True, db_index=True)

    class Meta:
        db_table = "pycrmkit_contacts"
        ordering = ("created_at", "id")


class ContactEmailModel(models.Model):
    contact = models.ForeignKey(
        ContactModel,
        db_column="contact_id",
        on_delete=models.CASCADE,
        related_name="email_rows",
    )
    position = models.PositiveIntegerField(default=0)
    value = models.CharField(max_length=320)
    normalized = models.CharField(max_length=320, db_index=True)
    is_primary = models.BooleanField(default=False)
    verification = models.CharField(max_length=32)

    class Meta:
        db_table = "pycrmkit_contact_emails"
        ordering = ("position", "id")
        indexes = [
            models.Index(
                fields=("contact", "position"),
                name="ix_dj_contact_email_pos",
            )
        ]


class ContactPhoneModel(models.Model):
    contact = models.ForeignKey(
        ContactModel,
        db_column="contact_id",
        on_delete=models.CASCADE,
        related_name="phone_rows",
    )
    position = models.PositiveIntegerField(default=0)
    value = models.CharField(max_length=64)
    normalized = models.CharField(max_length=64, db_index=True)
    is_primary = models.BooleanField(default=False)
    verification = models.CharField(max_length=32)

    class Meta:
        db_table = "pycrmkit_contact_phones"
        ordering = ("position", "id")


class ContactAddressModel(models.Model):
    contact = models.ForeignKey(
        ContactModel,
        db_column="contact_id",
        on_delete=models.CASCADE,
        related_name="address_rows",
    )
    position = models.PositiveIntegerField(default=0)
    line1 = models.CharField(max_length=511)
    line2 = models.CharField(max_length=511, null=True)
    city = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=64, null=True)
    region = models.CharField(max_length=255, null=True)
    country_code = models.CharField(max_length=2, null=True, db_index=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "pycrmkit_contact_addresses"
        ordering = ("position", "id")


class OrganizationModel(_TimestampedModel):
    id = models.CharField(max_length=36, primary_key=True)
    legal_name = models.CharField(max_length=511, db_index=True)
    trading_name = models.CharField(max_length=511, null=True)
    display_name = models.CharField(max_length=511, null=True)
    registration_number = models.CharField(max_length=255, null=True, db_index=True)
    tax_id = models.CharField(max_length=255, null=True, db_index=True)
    status = models.CharField(max_length=32, db_index=True)
    owner_id = models.CharField(max_length=255, null=True, db_index=True)
    source = models.CharField(max_length=255, null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)
    archived_at = models.DateTimeField(null=True, db_index=True)

    class Meta:
        db_table = "pycrmkit_organizations"
        ordering = ("created_at", "id")


class OrganizationDomainModel(models.Model):
    organization = models.ForeignKey(
        OrganizationModel,
        db_column="organization_id",
        on_delete=models.CASCADE,
        related_name="domain_rows",
    )
    position = models.PositiveIntegerField(default=0)
    value = models.CharField(max_length=253)
    normalized = models.CharField(max_length=253, db_index=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "pycrmkit_organization_domains"
        ordering = ("position", "id")


class OrganizationAddressModel(models.Model):
    organization = models.ForeignKey(
        OrganizationModel,
        db_column="organization_id",
        on_delete=models.CASCADE,
        related_name="address_rows",
    )
    position = models.PositiveIntegerField(default=0)
    line1 = models.CharField(max_length=511)
    line2 = models.CharField(max_length=511, null=True)
    city = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=64, null=True)
    region = models.CharField(max_length=255, null=True)
    country_code = models.CharField(max_length=2, null=True, db_index=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "pycrmkit_organization_addresses"
        ordering = ("position", "id")


class ExternalIdentityModel(_TimestampedModel):
    id = models.CharField(max_length=36, primary_key=True)
    system = models.CharField(max_length=128)
    external_id = models.CharField(max_length=512)
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=36)
    metadata_json = models.JSONField(db_column="metadata", default=dict)

    class Meta:
        db_table = "pycrmkit_external_identities"
        ordering = ("system", "external_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("system", "external_id"),
                name="uq_dj_external_identity_system_id",
            )
        ]
        indexes = [
            models.Index(
                fields=("entity_type", "entity_id"),
                name="ix_dj_external_identity_entity",
            )
        ]


class RelationshipModel(_TimestampedModel):
    id = models.CharField(max_length=36, primary_key=True)
    source_kind = models.CharField(max_length=32)
    source_id = models.CharField(max_length=36)
    target_kind = models.CharField(max_length=32)
    target_id = models.CharField(max_length=36)
    relationship_type = models.CharField(max_length=128, db_index=True)
    valid_from = models.DateTimeField()
    role = models.CharField(max_length=255, null=True)
    title = models.CharField(max_length=255, null=True)
    is_primary = models.BooleanField(default=False)
    valid_until = models.DateTimeField(null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)

    class Meta:
        db_table = "pycrmkit_relationships"
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=("source_kind", "source_id"),
                name="ix_dj_relationship_source",
            ),
            models.Index(
                fields=("target_kind", "target_id"),
                name="ix_dj_relationship_target",
            ),
        ]


class SegmentModel(_TimestampedModel):
    id = models.CharField(max_length=36, primary_key=True)
    key = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    entity_kind = models.CharField(max_length=64, db_index=True)
    mode = models.CharField(max_length=32, db_index=True)
    description = models.CharField(max_length=2000, null=True)
    status = models.CharField(max_length=32, db_index=True)
    query_json = models.JSONField(db_column="query", null=True)
    saved_query_id = models.CharField(max_length=36, null=True, db_index=True)
    saved_query_revision = models.PositiveIntegerField(null=True)
    owner_id = models.CharField(max_length=36, null=True, db_index=True)
    revision = models.PositiveIntegerField(default=1)
    metadata_json = models.JSONField(db_column="metadata", default=dict)
    archived_at = models.DateTimeField(null=True, db_index=True)

    class Meta:
        db_table = "pycrmkit_segments"
        ordering = ("created_at", "id")


class SegmentMemberModel(models.Model):
    segment = models.ForeignKey(
        SegmentModel,
        db_column="segment_id",
        on_delete=models.CASCADE,
        related_name="member_rows",
    )
    entity_kind = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=36)
    added_at = models.DateTimeField()
    source = models.CharField(max_length=120)
    actor_id = models.CharField(max_length=255, null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)

    class Meta:
        db_table = "pycrmkit_segment_members"
        ordering = ("added_at", "entity_kind", "entity_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("segment", "entity_kind", "entity_id"),
                name="uq_dj_segment_members_target",
            )
        ]
        indexes = [
            models.Index(
                fields=("entity_kind", "entity_id"),
                name="ix_dj_segment_members_entity",
            )
        ]


class SavedQueryModel(_TimestampedModel):
    row_id = models.BigAutoField(primary_key=True)
    query_id = models.CharField(max_length=36, db_column="id")
    revision = models.PositiveIntegerField()
    key = models.CharField(max_length=120, db_index=True)
    name = models.CharField(max_length=200)
    entity_kind = models.CharField(max_length=64, db_index=True)
    expression_json = models.JSONField(db_column="expression")
    ordering_json = models.JSONField(db_column="ordering", default=list)
    owner_id = models.CharField(max_length=36, null=True, db_index=True)
    visibility = models.CharField(max_length=32, db_index=True)
    status = models.CharField(max_length=32, db_index=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)
    archived_at = models.DateTimeField(null=True, db_index=True)

    class Meta:
        db_table = "pycrmkit_saved_queries"
        ordering = ("query_id", "revision")
        constraints = [
            models.UniqueConstraint(
                fields=("query_id", "revision"),
                name="uq_dj_saved_queries_id_revision",
            ),
            models.UniqueConstraint(
                fields=("key", "revision"),
                name="uq_dj_saved_queries_key_revision",
            ),
        ]
        indexes = [
            models.Index(
                fields=("query_id", "revision"),
                name="ix_dj_saved_query_rev",
            )
        ]



class CampaignModel(_TimestampedModel):
    """Campaign aggregate persistence; the domain owns business state and time."""

    id = models.CharField(max_length=36, primary_key=True)
    key = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=2000, null=True)
    status = models.CharField(max_length=32, db_index=True)
    starts_at = models.DateTimeField(null=True)
    ends_at = models.DateTimeField(null=True)
    owner_id = models.CharField(max_length=36, null=True, db_index=True)
    revision = models.PositiveIntegerField()
    metadata_json = models.JSONField(db_column="metadata", default=dict)
    archived_at = models.DateTimeField(null=True, db_index=True)

    class Meta:
        db_table = "pycrmkit_campaigns"
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=("created_at",),
                name="ix_dj_campaign_created",
            ),
        ]


class CampaignMemberModel(models.Model):
    """Direct audience membership, independent from Segment captures."""

    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(
        CampaignModel,
        db_column="campaign_id",
        on_delete=models.CASCADE,
        related_name="member_rows",
    )
    entity_kind = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=36)
    added_at = models.DateTimeField()
    source = models.CharField(max_length=120)
    actor_id = models.CharField(max_length=255, null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)

    class Meta:
        db_table = "pycrmkit_campaign_members"
        ordering = ("added_at", "entity_kind", "entity_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("campaign", "entity_kind", "entity_id"),
                name="uq_dj_campaign_member",
            ),
        ]
        indexes = [
            models.Index(
                fields=("entity_kind", "entity_id"),
                name="ix_dj_campaign_member_entity",
            ),
        ]


class CampaignSegmentSourceModel(models.Model):
    """Persistent Segment snapshot source with an internal-only surrogate PK."""

    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(
        CampaignModel,
        db_column="campaign_id",
        on_delete=models.CASCADE,
        related_name="segment_source_rows",
    )
    segment_id = models.CharField(max_length=36, db_index=True)
    segment_revision = models.PositiveIntegerField()
    entity_kind = models.CharField(max_length=64)
    attached_at = models.DateTimeField()
    captured_at = models.DateTimeField()
    member_count = models.PositiveIntegerField()
    actor_id = models.CharField(max_length=255, null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)

    class Meta:
        db_table = "pycrmkit_campaign_segment_sources"
        ordering = ("attached_at", "segment_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("campaign", "segment_id"),
                name="uq_dj_campaign_source",
            ),
        ]
        indexes = [
            models.Index(
                fields=("campaign", "attached_at"),
                name="ix_dj_campaign_src_attached",
            ),
        ]


class CampaignSegmentMemberModel(models.Model):
    """Captured member owned by its exact, persistently materialized source."""

    id = models.BigAutoField(primary_key=True)
    source = models.ForeignKey(
        CampaignSegmentSourceModel,
        db_column="source_id",
        on_delete=models.CASCADE,
        related_name="captured_member_rows",
    )
    entity_kind = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=36)

    class Meta:
        db_table = "pycrmkit_campaign_segment_members"
        ordering = ("entity_kind", "entity_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("source", "entity_kind", "entity_id"),
                name="uq_dj_campaign_snapshot",
            ),
        ]
        indexes = [
            models.Index(
                fields=("entity_kind", "entity_id"),
                name="ix_dj_campaign_snap_entity",
            ),
        ]


class CampaignAttributionModel(models.Model):
    """Campaign attribution; blank external_ref is the DB form of None."""

    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(
        CampaignModel,
        db_column="campaign_id",
        on_delete=models.CASCADE,
        related_name="attribution_rows",
    )
    target_kind = models.CharField(max_length=64)
    target_id = models.CharField(max_length=36)
    source = models.CharField(max_length=120, db_index=True)
    external_ref = models.CharField(max_length=512, default="")
    recorded_at = models.DateTimeField()
    actor_id = models.CharField(max_length=255, null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)

    class Meta:
        db_table = "pycrmkit_campaign_attributions"
        ordering = ("recorded_at", "source", "target_kind", "target_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "campaign",
                    "target_kind",
                    "target_id",
                    "source",
                    "external_ref",
                ),
                name="uq_dj_campaign_attribution",
            ),
        ]
        indexes = [
            models.Index(
                fields=("target_kind", "target_id"),
                name="ix_dj_campaign_attr_target",
            ),
            models.Index(
                fields=("campaign", "recorded_at"),
                name="ix_dj_campaign_attr_date",
            ),
        ]


class CampaignCommunicationLinkModel(models.Model):
    """Campaign-owned reference to a CommunicationRecord (not an FK)."""

    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(
        CampaignModel,
        db_column="campaign_id",
        on_delete=models.CASCADE,
        related_name="communication_link_rows",
    )
    communication_id = models.CharField(max_length=36, db_index=True)
    linked_at = models.DateTimeField()
    role = models.CharField(max_length=120)
    actor_id = models.CharField(max_length=255, null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)

    class Meta:
        db_table = "pycrmkit_campaign_communication_links"
        ordering = ("linked_at", "communication_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("campaign", "communication_id"),
                name="uq_dj_campaign_link",
            ),
        ]
        indexes = [
            models.Index(
                fields=("campaign", "linked_at"),
                name="ix_dj_campaign_link_date",
            ),
        ]



class CommunicationRecordModel(_TimestampedModel):
    """Django-owned lightweight CRM CommunicationRecord persistence."""

    id = models.CharField(max_length=36, primary_key=True)
    channel = models.CharField(max_length=32, db_index=True)
    direction = models.CharField(max_length=32)
    occurred_at = models.DateTimeField(db_index=True)
    counterparties_json = models.JSONField(default=list)
    references_json = models.JSONField(default=list)
    subject = models.CharField(max_length=500, null=True)
    intent_id = models.CharField(max_length=36, null=True, unique=True)
    delivery_attempt_id = models.CharField(max_length=36, null=True, unique=True)
    external_id = models.CharField(max_length=500, null=True, db_index=True)
    delivery_status = models.CharField(max_length=32, null=True)
    last_delivery_event_at = models.DateTimeField(null=True)
    metadata_json = models.JSONField(db_column="metadata", default=dict)

    class Meta:
        db_table = "pycrmkit_communication_records"
        ordering = ("-occurred_at", "id")


__all__ = [
    "CommunicationRecordModel",
    "CampaignAttributionModel",
    "CampaignCommunicationLinkModel",
    "CampaignMemberModel",
    "CampaignModel",
    "CampaignSegmentMemberModel",
    "CampaignSegmentSourceModel",
    "ContactAddressModel",
    "ContactEmailModel",
    "ContactModel",
    "ContactPhoneModel",
    "ExternalIdentityModel",
    "OrganizationAddressModel",
    "OrganizationDomainModel",
    "OrganizationModel",
    "RelationshipModel",
    "SavedQueryModel",
    "SegmentMemberModel",
    "SegmentModel",
]
