"""WSGI entry point for the PyCRMKit Django reference application."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pycrmkit_example.settings")

application = get_wsgi_application()
