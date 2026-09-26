# Generated manually for PyCRMKit 0.9.0a1 external identities.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pycrmkit_crm", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalIdentityModel",
            fields=[
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                ("id", models.CharField(max_length=36, primary_key=True, serialize=False)),
                ("system", models.CharField(max_length=128)),
                ("external_id", models.CharField(max_length=512)),
                ("entity_type", models.CharField(max_length=64)),
                ("entity_id", models.CharField(max_length=36)),
                ("metadata_json", models.JSONField(db_column="metadata", default=dict)),
            ],
            options={
                "db_table": "pycrmkit_external_identities",
                "ordering": ("system", "external_id", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="externalidentitymodel",
            constraint=models.UniqueConstraint(
                fields=("system", "external_id"),
                name="uq_dj_external_identity_system_id",
            ),
        ),
        migrations.AddIndex(
            model_name="externalidentitymodel",
            index=models.Index(
                fields=["entity_type", "entity_id"],
                name="ix_dj_external_identity_entity",
            ),
        ),
    ]
