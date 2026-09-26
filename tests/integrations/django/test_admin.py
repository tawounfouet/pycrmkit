"""Django admin smoke tests for the optional adapter."""

from __future__ import annotations

from django.contrib import admin

from pycrmkit.integrations.django.admin import (
    ContactModelAdmin,
    OrganizationModelAdmin,
    RelationshipModelAdmin,
)
from pycrmkit.integrations.django.models import (
    ContactModel,
    OrganizationModel,
    RelationshipModel,
)


def test_core_models_are_registered_with_admin_helpers() -> None:
    assert admin.site.is_registered(ContactModel)
    assert admin.site.is_registered(OrganizationModel)
    assert admin.site.is_registered(RelationshipModel)

    assert isinstance(admin.site._registry[ContactModel], ContactModelAdmin)
    assert isinstance(admin.site._registry[OrganizationModel], OrganizationModelAdmin)
    assert isinstance(admin.site._registry[RelationshipModel], RelationshipModelAdmin)


def test_contact_and_organization_admins_expose_embedded_rows_inline() -> None:
    contact_admin = admin.site._registry[ContactModel]
    organization_admin = admin.site._registry[OrganizationModel]

    assert len(contact_admin.inlines) == 3
    assert len(organization_admin.inlines) == 2
