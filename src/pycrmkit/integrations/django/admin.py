"""Django admin helpers for PyCRMKit persistence representations."""

from __future__ import annotations

from typing import TYPE_CHECKING

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


if TYPE_CHECKING:
    class _ContactEmailInlineBase(admin.TabularInline[ContactModel, ContactEmailModel]):
        pass

    class _ContactPhoneInlineBase(admin.TabularInline[ContactModel, ContactPhoneModel]):
        pass

    class _ContactAddressInlineBase(admin.StackedInline[ContactModel, ContactAddressModel]):
        pass

    class _ContactModelAdminBase(admin.ModelAdmin[ContactModel]):
        pass

    class _OrganizationDomainInlineBase(admin.TabularInline[OrganizationModel, OrganizationDomainModel]):
        pass

    class _OrganizationAddressInlineBase(admin.StackedInline[OrganizationModel, OrganizationAddressModel]):
        pass

    class _OrganizationModelAdminBase(admin.ModelAdmin[OrganizationModel]):
        pass

    class _RelationshipModelAdminBase(admin.ModelAdmin[RelationshipModel]):
        pass
else:
    _ContactEmailInlineBase = admin.TabularInline
    _ContactPhoneInlineBase = admin.TabularInline
    _ContactAddressInlineBase = admin.StackedInline
    _ContactModelAdminBase = admin.ModelAdmin
    _OrganizationDomainInlineBase = admin.TabularInline
    _OrganizationAddressInlineBase = admin.StackedInline
    _OrganizationModelAdminBase = admin.ModelAdmin
    _RelationshipModelAdminBase = admin.ModelAdmin


class ContactEmailInline(_ContactEmailInlineBase):
    model = ContactEmailModel
    extra = 0


class ContactPhoneInline(_ContactPhoneInlineBase):
    model = ContactPhoneModel
    extra = 0


class ContactAddressInline(_ContactAddressInlineBase):
    model = ContactAddressModel
    extra = 0


@admin.register(ContactModel)
class ContactModelAdmin(_ContactModelAdminBase):
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


class OrganizationDomainInline(_OrganizationDomainInlineBase):
    model = OrganizationDomainModel
    extra = 0


class OrganizationAddressInline(_OrganizationAddressInlineBase):
    model = OrganizationAddressModel
    extra = 0


@admin.register(OrganizationModel)
class OrganizationModelAdmin(_OrganizationModelAdminBase):
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
class RelationshipModelAdmin(_RelationshipModelAdminBase):
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
