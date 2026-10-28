"""Add Django-owned CommunicationRecord storage for Campaign linkage.

Separate from Campaign migration 0004. This is a narrow record-store capability
and not a full Django implementation of the CommunicationRepository protocol.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pycrmkit_crm", "0004_campaign_persistence"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunicationRecordModel",
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
                ("channel", models.CharField(max_length=32, db_index=True)),
                ("direction", models.CharField(max_length=32)),
                ("occurred_at", models.DateTimeField(db_index=True)),
                ("counterparties_json", models.JSONField(default=list)),
                ("references_json", models.JSONField(default=list)),
                ("subject", models.CharField(max_length=500, null=True)),
                (
                    "intent_id",
                    models.CharField(max_length=36, null=True, unique=True),
                ),
                (
                    "delivery_attempt_id",
                    models.CharField(max_length=36, null=True, unique=True),
                ),
                (
                    "external_id",
                    models.CharField(max_length=500, null=True, db_index=True),
                ),
                (
                    "delivery_status",
                    models.CharField(max_length=32, null=True),
                ),
                ("last_delivery_event_at", models.DateTimeField(null=True)),
                (
                    "metadata_json",
                    models.JSONField(db_column="metadata", default=dict),
                ),
            ],
            options={
                "db_table": "pycrmkit_communication_records",
                "ordering": ("-occurred_at", "id"),
            },
        ),
    ]
