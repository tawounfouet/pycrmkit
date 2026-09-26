"""Minimal Django environment for optional DRF integration tests."""

from __future__ import annotations

import django
from django.conf import settings

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
        ROOT_URLCONF="tests.integrations.drf.urls",
        REST_FRAMEWORK={
            "UNAUTHENTICATED_USER": None,
            "EXCEPTION_HANDLER": (
                "pycrmkit.integrations.django.drf.errors."
                "pycrmkit_exception_handler"
            ),
        },
    )

django.setup()
