"""Django application bootstrap for the optional PyCRMKit adapter."""

from django.apps import AppConfig


class PyCRMKitDjangoConfig(AppConfig):
    """Register PyCRMKit's Django persistence adapter without domain side effects."""

    name = "pycrmkit.integrations.django"
    label = "pycrmkit_crm"
    verbose_name = "PyCRMKit CRM"
    default_auto_field = "django.db.models.BigAutoField"


__all__ = ["PyCRMKitDjangoConfig"]
