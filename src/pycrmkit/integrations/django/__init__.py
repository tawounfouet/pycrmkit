"""Optional Django integration for PyCRMKit."""

from __future__ import annotations

try:
    from pycrmkit.integrations.django.apps import PyCRMKitDjangoConfig
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in clean-install smoke.
    if exc.name == "django":
        raise RuntimeError(
            'Django support requires the optional dependency: pip install "pycrmkit[django]"'
        ) from exc
    raise

__all__ = ["PyCRMKitDjangoConfig"]
