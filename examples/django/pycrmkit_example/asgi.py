"""ASGI entry point for the PyCRMKit Django reference application."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pycrmkit_example.settings")

application = get_asgi_application()
