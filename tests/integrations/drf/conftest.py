"""Minimal Django environment for optional DRF integration tests."""

from __future__ import annotations

from collections.abc import Iterator

import django
import pytest
from django.conf import settings
from django.test import override_settings

if not settings.configured:
    settings.configure(
        SECRET_KEY="pycrmkit-drf-tests",
        INSTALLED_APPS=[],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        USE_TZ=True,
        TIME_ZONE="UTC",
    )

django.setup()


@pytest.fixture(autouse=True)
def drf_test_settings() -> Iterator[None]:
    """Keep DRF URL/error settings isolated even in the full test process."""

    with override_settings(
        ROOT_URLCONF="tests.integrations.drf.urls",
        REST_FRAMEWORK={
            "UNAUTHENTICATED_USER": None,
            "EXCEPTION_HANDLER": (
                "pycrmkit.integrations.django.drf.errors."
                "pycrmkit_exception_handler"
            ),
        },
    ):
        yield
