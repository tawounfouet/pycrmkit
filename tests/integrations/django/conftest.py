"""Minimal Django test environment for the optional adapter."""

from __future__ import annotations

import django
import pytest
from django.conf import settings
from django.db import connection

if not settings.configured:
    settings.configure(
        SECRET_KEY="pycrmkit-django-tests",
        INSTALLED_APPS=[
            "pycrmkit.integrations.django.apps.PyCRMKitDjangoConfig",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        USE_TZ=True,
        TIME_ZONE="UTC",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )

django.setup()

from pycrmkit.integrations.django.models import (  # noqa: E402
    ContactAddressModel,
    ContactEmailModel,
    ContactModel,
    ContactPhoneModel,
    OrganizationAddressModel,
    OrganizationDomainModel,
    OrganizationModel,
    RelationshipModel,
)

DJANGO_MODELS = (
    ContactModel,
    ContactEmailModel,
    ContactPhoneModel,
    ContactAddressModel,
    OrganizationModel,
    OrganizationDomainModel,
    OrganizationAddressModel,
    RelationshipModel,
)


@pytest.fixture(scope="session", autouse=True)
def django_schema() -> None:
    """Create the alpha schema without introducing Django migrations before 0.8.0b1."""

    with connection.schema_editor() as schema_editor:
        for model in DJANGO_MODELS:
            schema_editor.create_model(model)
    yield
    with connection.schema_editor() as schema_editor:
        for model in reversed(DJANGO_MODELS):
            schema_editor.delete_model(model)


@pytest.fixture(autouse=True)
def clean_django_rows(django_schema: None) -> None:
    """Keep reusable contract cases isolated."""

    RelationshipModel.objects.all().delete()
    ContactModel.objects.all().delete()
    OrganizationModel.objects.all().delete()
