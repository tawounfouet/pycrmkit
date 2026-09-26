"""Configuration bridge for optional DRF integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from pycrmkit import CRM

CRMFactory = Callable[[], CRM]
CRM_FACTORY_SETTING = "PYCRMKIT_CRM_FACTORY"


def get_crm_factory() -> CRMFactory:
    """Resolve the application-owned CRM factory from Django settings."""

    value = getattr(settings, CRM_FACTORY_SETTING, None)
    if value is None:
        raise ImproperlyConfigured(
            f"{CRM_FACTORY_SETTING} must be configured with a callable or dotted path"
        )

    if isinstance(value, str):
        resolved = import_string(value)
    else:
        resolved = value

    if not callable(resolved):
        raise ImproperlyConfigured(
            f"{CRM_FACTORY_SETTING} must resolve to a callable returning pycrmkit.CRM"
        )
    return cast(CRMFactory, resolved)


__all__ = ["CRMFactory", "CRM_FACTORY_SETTING", "get_crm_factory"]
