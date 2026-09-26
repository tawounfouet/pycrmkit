# Generated for PyCRMKit 0.8.0b1 / Django 5.2.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ContactModel",
            fields=[
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                ("id", models.CharField(max_length=36, primary_key=True, serialize=False)),
                ("first_name", models.CharField(max_length=255, null=True)),
                ("last_name", models.CharField(max_length=255, null=True)),
                ("display_name", models.CharField(max_length=511, null=True)),
                ("status", models.CharField(db_index=True, max_length=32)),
                ("owner_id", models.CharField(db_index=True, max_length=255, null=True)),
                ("source", models.CharField(max_length=255, null=True)),
                ("metadata_json", models.JSONField(db_column="metadata", default=dict)),
                ("archived_at", models.DateTimeField(db_index=True, null=True)),
            ],
            options={
                "db_table": "pycrmkit_contacts",
                "ordering": ("created_at", "id"),
            },
        ),
        migrations.CreateModel(
            name="OrganizationModel",
            fields=[
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                ("id", models.CharField(max_length=36, primary_key=True, serialize=False)),
                ("legal_name", models.CharField(db_index=True, max_length=511)),
                ("trading_name", models.CharField(max_length=511, null=True)),
                ("display_name", models.CharField(max_length=511, null=True)),
                ("registration_number", models.CharField(db_index=True, max_length=255, null=True)),
                ("tax_id", models.CharField(db_index=True, max_length=255, null=True)),
                ("status", models.CharField(db_index=True, max_length=32)),
                ("owner_id", models.CharField(db_index=True, max_length=255, null=True)),
                ("source", models.CharField(max_length=255, null=True)),
                ("metadata_json", models.JSONField(db_column="metadata", default=dict)),
                ("archived_at", models.DateTimeField(db_index=True, null=True)),
            ],
            options={
                "db_table": "pycrmkit_organizations",
                "ordering": ("created_at", "id"),
            },
        ),
        migrations.CreateModel(
            name="RelationshipModel",
            fields=[
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                ("id", models.CharField(max_length=36, primary_key=True, serialize=False)),
                ("source_kind", models.CharField(max_length=32)),
                ("source_id", models.CharField(max_length=36)),
                ("target_kind", models.CharField(max_length=32)),
                ("target_id", models.CharField(max_length=36)),
                ("relationship_type", models.CharField(db_index=True, max_length=128)),
                ("valid_from", models.DateTimeField()),
                ("role", models.CharField(max_length=255, null=True)),
                ("title", models.CharField(max_length=255, null=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("valid_until", models.DateTimeField(null=True)),
                ("metadata_json", models.JSONField(db_column="metadata", default=dict)),
            ],
            options={
                "db_table": "pycrmkit_relationships",
                "ordering": ("created_at", "id"),
                "indexes": [
                    models.Index(fields=["source_kind", "source_id"], name="ix_dj_relationship_source"),
                    models.Index(fields=["target_kind", "target_id"], name="ix_dj_relationship_target"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ContactAddressModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("line1", models.CharField(max_length=511)),
                ("line2", models.CharField(max_length=511, null=True)),
                ("city", models.CharField(max_length=255)),
                ("postal_code", models.CharField(max_length=64, null=True)),
                ("region", models.CharField(max_length=255, null=True)),
                ("country_code", models.CharField(db_index=True, max_length=2, null=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("contact", models.ForeignKey(db_column="contact_id", on_delete=django.db.models.deletion.CASCADE, related_name="address_rows", to="pycrmkit_crm.contactmodel")),
            ],
            options={
                "db_table": "pycrmkit_contact_addresses",
                "ordering": ("position", "id"),
            },
        ),
        migrations.CreateModel(
            name="ContactEmailModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("value", models.CharField(max_length=320)),
                ("normalized", models.CharField(db_index=True, max_length=320)),
                ("is_primary", models.BooleanField(default=False)),
                ("verification", models.CharField(max_length=32)),
                ("contact", models.ForeignKey(db_column="contact_id", on_delete=django.db.models.deletion.CASCADE, related_name="email_rows", to="pycrmkit_crm.contactmodel")),
            ],
            options={
                "db_table": "pycrmkit_contact_emails",
                "ordering": ("position", "id"),
                "indexes": [
                    models.Index(fields=["contact", "position"], name="ix_dj_contact_email_pos")
                ],
            },
        ),
        migrations.CreateModel(
            name="ContactPhoneModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("value", models.CharField(max_length=64)),
                ("normalized", models.CharField(db_index=True, max_length=64)),
                ("is_primary", models.BooleanField(default=False)),
                ("verification", models.CharField(max_length=32)),
                ("contact", models.ForeignKey(db_column="contact_id", on_delete=django.db.models.deletion.CASCADE, related_name="phone_rows", to="pycrmkit_crm.contactmodel")),
            ],
            options={
                "db_table": "pycrmkit_contact_phones",
                "ordering": ("position", "id"),
            },
        ),
        migrations.CreateModel(
            name="OrganizationAddressModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("line1", models.CharField(max_length=511)),
                ("line2", models.CharField(max_length=511, null=True)),
                ("city", models.CharField(max_length=255)),
                ("postal_code", models.CharField(max_length=64, null=True)),
                ("region", models.CharField(max_length=255, null=True)),
                ("country_code", models.CharField(db_index=True, max_length=2, null=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("organization", models.ForeignKey(db_column="organization_id", on_delete=django.db.models.deletion.CASCADE, related_name="address_rows", to="pycrmkit_crm.organizationmodel")),
            ],
            options={
                "db_table": "pycrmkit_organization_addresses",
                "ordering": ("position", "id"),
            },
        ),
        migrations.CreateModel(
            name="OrganizationDomainModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("value", models.CharField(max_length=253)),
                ("normalized", models.CharField(db_index=True, max_length=253)),
                ("is_primary", models.BooleanField(default=False)),
                ("organization", models.ForeignKey(db_column="organization_id", on_delete=django.db.models.deletion.CASCADE, related_name="domain_rows", to="pycrmkit_crm.organizationmodel")),
            ],
            options={
                "db_table": "pycrmkit_organization_domains",
                "ordering": ("position", "id"),
            },
        ),
    ]
