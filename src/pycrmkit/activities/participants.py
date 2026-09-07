"""Activity participants and CRM entity references."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from pycrmkit.core.references import EntityReference
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError


def normalize_participant_role(value: str | None) -> str | None:
    """Normalize an optional participant role without imposing a closed taxonomy."""
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > 120:
        raise ValidationError(
            "activity participant role must be at most 120 characters",
            code="activity.participant.role_too_long",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class ActivityParticipant(ValueObject):
    """Reference one CRM entity participating in an activity."""

    reference: EntityReference
    role: str | None = None
    is_primary: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.reference, EntityReference):
            raise ValidationError(
                "activity participants require an EntityReference",
                code="activity.participant.reference.invalid",
            )
        object.__setattr__(self, "role", normalize_participant_role(self.role))
