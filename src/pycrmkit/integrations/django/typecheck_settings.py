"""Minimal settings module used only by django-stubs during static analysis."""

SECRET_KEY = "pycrmkit-typecheck"
INSTALLED_APPS = [
    "pycrmkit.integrations.django.apps.PyCRMKitDjangoConfig",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
