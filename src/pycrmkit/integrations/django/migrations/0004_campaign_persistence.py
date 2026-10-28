"""Add Django-owned Campaign metadata, audience, snapshots and linkage.

This additive migration is NOT compatible with reusing Alembic-managed
Campaign tables: the Django source/snapshot FK mapping differs from b1.
Downgrading to 0003 deletes the six Django Campaign tables and their rows.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pycrmkit_crm", "0003_segmentation"),
    ]

    operations = [
        migrations.CreateModel(
            name="CampaignModel",
            fields=[
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                (
                    "id",
                    models.CharField(
                        max_length=36,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("key", models.CharField(max_length=120, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.CharField(max_length=2000, null=True)),
                ("status", models.CharField(max_length=32, db_index=True)),
                ("starts_at", models.DateTimeField(null=True)),
                ("ends_at", models.DateTimeField(null=True)),
                (
                    "owner_id",
                    models.CharField(max_length=36, null=True, db_index=True),
                ),
                ("revision", models.PositiveIntegerField()),
                (
                    "metadata_json",
                    models.JSONField(db_column="metadata", default=dict),
                ),
                ("archived_at", models.DateTimeField(null=True, db_index=True)),
            ],
            options={
                "db_table": "pycrmkit_campaigns",
                "ordering": ("created_at", "id"),
            },
        ),
        migrations.CreateModel(
            name="CampaignMemberModel",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("entity_kind", models.CharField(max_length=64)),
                ("entity_id", models.CharField(max_length=36)),
                ("added_at", models.DateTimeField()),
                ("source", models.CharField(max_length=120)),
                ("actor_id", models.CharField(max_length=255, null=True)),
                (
                    "metadata_json",
                    models.JSONField(db_column="metadata", default=dict),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        db_column="campaign_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="member_rows",
                        to="pycrmkit_crm.campaignmodel",
                    ),
                ),
            ],
            options={
                "db_table": "pycrmkit_campaign_members",
                "ordering": ("added_at", "entity_kind", "entity_id", "id"),
            },
        ),
        migrations.CreateModel(
            name="CampaignSegmentSourceModel",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("segment_id", models.CharField(max_length=36, db_index=True)),
                ("segment_revision", models.PositiveIntegerField()),
                ("entity_kind", models.CharField(max_length=64)),
                ("attached_at", models.DateTimeField()),
                ("captured_at", models.DateTimeField()),
                ("member_count", models.PositiveIntegerField()),
                ("actor_id", models.CharField(max_length=255, null=True)),
                (
                    "metadata_json",
                    models.JSONField(db_column="metadata", default=dict),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        db_column="campaign_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="segment_source_rows",
                        to="pycrmkit_crm.campaignmodel",
                    ),
                ),
            ],
            options={
                "db_table": "pycrmkit_campaign_segment_sources",
                "ordering": ("attached_at", "segment_id", "id"),
            },
        ),
        migrations.CreateModel(
            name="CampaignSegmentMemberModel",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("entity_kind", models.CharField(max_length=64)),
                ("entity_id", models.CharField(max_length=36)),
                (
                    "source",
                    models.ForeignKey(
                        db_column="source_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="captured_member_rows",
                        to="pycrmkit_crm.campaignsegmentsourcemodel",
                    ),
                ),
            ],
            options={
                "db_table": "pycrmkit_campaign_segment_members",
                "ordering": ("entity_kind", "entity_id", "id"),
            },
        ),
        migrations.CreateModel(
            name="CampaignAttributionModel",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("target_kind", models.CharField(max_length=64)),
                ("target_id", models.CharField(max_length=36)),
                ("source", models.CharField(max_length=120, db_index=True)),
                (
                    "external_ref",
                    models.CharField(max_length=512, default=""),
                ),
                ("recorded_at", models.DateTimeField()),
                ("actor_id", models.CharField(max_length=255, null=True)),
                (
                    "metadata_json",
                    models.JSONField(db_column="metadata", default=dict),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        db_column="campaign_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attribution_rows",
                        to="pycrmkit_crm.campaignmodel",
                    ),
                ),
            ],
            options={
                "db_table": "pycrmkit_campaign_attributions",
                "ordering": (
                    "recorded_at",
                    "source",
                    "target_kind",
                    "target_id",
                    "id",
                ),
            },
        ),
        migrations.CreateModel(
            name="CampaignCommunicationLinkModel",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "communication_id",
                    models.CharField(max_length=36, db_index=True),
                ),
                ("linked_at", models.DateTimeField()),
                ("role", models.CharField(max_length=120)),
                ("actor_id", models.CharField(max_length=255, null=True)),
                (
                    "metadata_json",
                    models.JSONField(db_column="metadata", default=dict),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        db_column="campaign_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="communication_link_rows",
                        to="pycrmkit_crm.campaignmodel",
                    ),
                ),
            ],
            options={
                "db_table": "pycrmkit_campaign_communication_links",
                "ordering": ("linked_at", "communication_id", "id"),
            },
        ),
        migrations.AddIndex(
            model_name="campaignmodel",
            index=models.Index(
                fields=["created_at"], name="ix_dj_campaign_created"
            ),
        ),
        migrations.AddConstraint(
            model_name="campaignmembermodel",
            constraint=models.UniqueConstraint(
                fields=("campaign", "entity_kind", "entity_id"),
                name="uq_dj_campaign_member",
            ),
        ),
        migrations.AddIndex(
            model_name="campaignmembermodel",
            index=models.Index(
                fields=["entity_kind", "entity_id"],
                name="ix_dj_campaign_member_entity",
            ),
        ),
        migrations.AddConstraint(
            model_name="campaignsegmentsourcemodel",
            constraint=models.UniqueConstraint(
                fields=("campaign", "segment_id"),
                name="uq_dj_campaign_source",
            ),
        ),
        migrations.AddIndex(
            model_name="campaignsegmentsourcemodel",
            index=models.Index(
                fields=["campaign", "attached_at"],
                name="ix_dj_campaign_src_attached",
            ),
        ),
        migrations.AddConstraint(
            model_name="campaignsegmentmembermodel",
            constraint=models.UniqueConstraint(
                fields=("source", "entity_kind", "entity_id"),
                name="uq_dj_campaign_snapshot",
            ),
        ),
        migrations.AddIndex(
            model_name="campaignsegmentmembermodel",
            index=models.Index(
                fields=["entity_kind", "entity_id"],
                name="ix_dj_campaign_snap_entity",
            ),
        ),
        migrations.AddConstraint(
            model_name="campaignattributionmodel",
            constraint=models.UniqueConstraint(
                fields=(
                    "campaign",
                    "target_kind",
                    "target_id",
                    "source",
                    "external_ref",
                ),
                name="uq_dj_campaign_attribution",
            ),
        ),
        migrations.AddIndex(
            model_name="campaignattributionmodel",
            index=models.Index(
                fields=["target_kind", "target_id"],
                name="ix_dj_campaign_attr_target",
            ),
        ),
        migrations.AddIndex(
            model_name="campaignattributionmodel",
            index=models.Index(
                fields=["campaign", "recorded_at"],
                name="ix_dj_campaign_attr_date",
            ),
        ),
        migrations.AddConstraint(
            model_name="campaigncommunicationlinkmodel",
            constraint=models.UniqueConstraint(
                fields=("campaign", "communication_id"),
                name="uq_dj_campaign_link",
            ),
        ),
        migrations.AddIndex(
            model_name="campaigncommunicationlinkmodel",
            index=models.Index(
                fields=["campaign", "linked_at"],
                name="ix_dj_campaign_link_date",
            ),
        ),
    ]
