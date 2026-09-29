# Generated for PyCRMKit 1.1.0b2 segmentation persistence.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pycrmkit_crm", "0002_external_identity"),
    ]

    operations = [
        migrations.CreateModel(
            name="SegmentModel",
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
                ("entity_kind", models.CharField(db_index=True, max_length=64)),
                ("mode", models.CharField(db_index=True, max_length=32)),
                ("description", models.CharField(max_length=2000, null=True)),
                ("status", models.CharField(db_index=True, max_length=32)),
                ("query_json", models.JSONField(db_column="query", null=True)),
                (
                    "saved_query_id",
                    models.CharField(
                        db_index=True,
                        max_length=36,
                        null=True,
                    ),
                ),
                (
                    "saved_query_revision",
                    models.PositiveIntegerField(null=True),
                ),
                (
                    "owner_id",
                    models.CharField(
                        db_index=True,
                        max_length=36,
                        null=True,
                    ),
                ),
                ("revision", models.PositiveIntegerField(default=1)),
                (
                    "metadata_json",
                    models.JSONField(db_column="metadata", default=dict),
                ),
                (
                    "archived_at",
                    models.DateTimeField(db_index=True, null=True),
                ),
            ],
            options={
                "db_table": "pycrmkit_segments",
                "ordering": ("created_at", "id"),
            },
        ),
        migrations.CreateModel(
            name="SavedQueryModel",
            fields=[
                (
                    "row_id",
                    models.BigAutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                (
                    "query_id",
                    models.CharField(
                        db_column="id",
                        max_length=36,
                    ),
                ),
                ("revision", models.PositiveIntegerField()),
                ("key", models.CharField(db_index=True, max_length=120)),
                ("name", models.CharField(max_length=200)),
                ("entity_kind", models.CharField(db_index=True, max_length=64)),
                (
                    "expression_json",
                    models.JSONField(db_column="expression"),
                ),
                (
                    "ordering_json",
                    models.JSONField(db_column="ordering", default=list),
                ),
                (
                    "owner_id",
                    models.CharField(
                        db_index=True,
                        max_length=36,
                        null=True,
                    ),
                ),
                ("visibility", models.CharField(db_index=True, max_length=32)),
                ("status", models.CharField(db_index=True, max_length=32)),
                (
                    "metadata_json",
                    models.JSONField(db_column="metadata", default=dict),
                ),
                (
                    "archived_at",
                    models.DateTimeField(db_index=True, null=True),
                ),
            ],
            options={
                "db_table": "pycrmkit_saved_queries",
                "ordering": ("query_id", "revision"),
            },
        ),
        migrations.CreateModel(
            name="SegmentMemberModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
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
                    "segment",
                    models.ForeignKey(
                        db_column="segment_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="member_rows",
                        to="pycrmkit_crm.segmentmodel",
                    ),
                ),
            ],
            options={
                "db_table": "pycrmkit_segment_members",
                "ordering": (
                    "added_at",
                    "entity_kind",
                    "entity_id",
                    "id",
                ),
            },
        ),
        migrations.AddConstraint(
            model_name="savedquerymodel",
            constraint=models.UniqueConstraint(
                fields=("query_id", "revision"),
                name="uq_dj_saved_queries_id_revision",
            ),
        ),
        migrations.AddConstraint(
            model_name="savedquerymodel",
            constraint=models.UniqueConstraint(
                fields=("key", "revision"),
                name="uq_dj_saved_queries_key_revision",
            ),
        ),
        migrations.AddIndex(
            model_name="savedquerymodel",
            index=models.Index(
                fields=["query_id", "revision"],
                name="ix_dj_saved_query_rev",
            ),
        ),
        migrations.AddConstraint(
            model_name="segmentmembermodel",
            constraint=models.UniqueConstraint(
                fields=("segment", "entity_kind", "entity_id"),
                name="uq_dj_segment_members_target",
            ),
        ),
        migrations.AddIndex(
            model_name="segmentmembermodel",
            index=models.Index(
                fields=["entity_kind", "entity_id"],
                name="ix_dj_segment_members_entity",
            ),
        ),
    ]
