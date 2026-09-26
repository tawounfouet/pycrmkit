"""Django ORM persistence models for the initial PyCRMKit adapter.

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


__all__ = [
    "ContactAddressModel",
    "ContactEmailModel",
    "ContactModel",
    "ContactPhoneModel",
    "ExternalIdentityModel",
    "OrganizationAddressModel",
    "OrganizationDomainModel",
    "OrganizationModel",
    "RelationshipModel",
]
