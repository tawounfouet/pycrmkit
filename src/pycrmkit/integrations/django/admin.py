"""Django admin helpers for PyCRMKit persistence representations."""

from __future__ import annotations

from django.contrib import admin

from pycrmkit.integrations.django.models import (
    ContactAddressModel,
    ContactEmailModel,
    ContactModel,
    ContactPhoneModel,
    OrganizationAddressModel,
    OrganizationDomainModel,
    OrganizationModel,
    RelationshipModel,
)


class ContactEmailInline(admin.TabularInline):
    model = ContactEmailModel
    extra = 0


class ContactPhoneInline(admin.TabularInline):
    model = ContactPhoneModel
    extra = 0


class ContactAddressInline(admin.StackedInline):
    model = ContactAddressModel
    extra = 0


@admin.register(ContactModel)
class ContactModelAdmin(admin.ModelAdmin):
    """Operational view over Contact persistence state."""

    list_display = ("id", "display_name", "status", "owner_id", "created_at", "archived_at")
    list_filter = ("status", "archived_at")
    search_fields = (
        "id",
        "first_name",
        "last_name",
        "display_name",
        "email_rows__normalized",
        "phone_rows__normalized",
    )
    readonly_fields = ("created_at", "updated_at")
    inlines = (ContactEmailInline, ContactPhoneInline, ContactAddressInline)


class OrganizationDomainInline(admin.TabularInline):
    model = OrganizationDomainModel
    extra = 0


class OrganizationAddressInline(admin.StackedInline):
    model = OrganizationAddressModel
    extra = 0


@admin.register(OrganizationModel)
class OrganizationModelAdmin(admin.ModelAdmin):
    """Operational view over Organization persistence state."""

    list_display = (
        "id",
        "legal_name",
        "display_name",
        "status",
        "owner_id",
        "created_at",
        "archived_at",
    )
    list_filter = ("status", "archived_at")
    search_fields = (
        "id",
        "legal_name",
        "trading_name",
        "display_name",
        "registration_number",
        "domain_rows__normalized",
    )
    readonly_fields = ("created_at", "updated_at")
    inlines = (OrganizationDomainInline, OrganizationAddressInline)


@admin.register(RelationshipModel)
class RelationshipModelAdmin(admin.ModelAdmin):
    """Operational view over directional CRM relationship persistence."""

    list_display = (
        "id",
        "relationship_type",
        "source_kind",
        "source_id",
        "target_kind",
        "target_id",
        "is_primary",
        "valid_from",
        "valid_until",
    )
    list_filter = ("relationship_type", "source_kind", "target_kind", "is_primary")
    search_fields = ("id", "source_id", "target_id", "role", "title")
    readonly_fields = ("created_at", "updated_at")


__all__ = ["ContactModelAdmin", "OrganizationModelAdmin", "RelationshipModelAdmin"]
