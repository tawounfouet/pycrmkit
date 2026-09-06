"""Public configuration and operation context for the PyCRMKit facade."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.core.events import EventId
from pycrmkit.exceptions import ValidationError


def _optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValidationError(
            f"{field_name} cannot be blank",
            code=f"crm.{field_name}.invalid",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class CRMConfig:
    """Stable configuration for cross-cutting facade behavior."""

    events_enabled: bool = True
    audit_enabled: bool = True
    default_actor_id: str | None = None
    default_correlation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "default_actor_id",
            _optional_text(self.default_actor_id, field_name="actor_id"),
        )
        object.__setattr__(
            self,
            "default_correlation_id",
            _optional_text(self.default_correlation_id, field_name="correlation_id"),
        )


@dataclass(frozen=True, slots=True)
class CRMContext:
    """Actor/correlation/causation metadata applied to facade mutations."""

    actor_id: str | None = None
    correlation_id: str | None = None
    causation_id: EventId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "actor_id",
            _optional_text(self.actor_id, field_name="actor_id"),
        )
        object.__setattr__(
            self,
            "correlation_id",
            _optional_text(self.correlation_id, field_name="correlation_id"),
        )
