"""Immutable append-oriented audit records."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from pycrmkit.core.ids import UUIDId
from pycrmkit.core.json import freeze_json_mapping, thaw_json_mapping
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError

_ACTION_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}(?:\.[a-z][a-z0-9_]{0,63})+$")


class AuditEntryId(UUIDId):
    """Strongly typed identifier for one immutable audit record."""


def _required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValidationError(
            f"{field_name} cannot be blank",
            code=f"audit.{field_name}.invalid",
        )
    return normalized


def _optional_text(value: str | None, *, field_name: str) -> str | None:
    return None if value is None else _required_text(value, field_name=field_name)


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Append-only system mutation record, distinct from customer timeline history."""

    id: AuditEntryId
    actor_id: str | None
    action: str
    entity_type: str
    entity_id: str
    occurred_at: datetime
    changes: Mapping[str, object] = field(default_factory=dict)
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        action = self.action.strip().casefold()
        if not _ACTION_PATTERN.fullmatch(action):
            raise ValidationError(
                "audit action must be a dotted lowercase identifier",
                code="audit.action.invalid",
                context={"action": self.action},
            )
        object.__setattr__(self, "action", action)
        object.__setattr__(
            self,
            "entity_type",
            _required_text(self.entity_type, field_name="entity_type").casefold(),
        )
        object.__setattr__(self, "entity_id", _required_text(self.entity_id, field_name="entity_id"))
        object.__setattr__(self, "actor_id", _optional_text(self.actor_id, field_name="actor_id"))
        object.__setattr__(
            self,
            "correlation_id",
            _optional_text(self.correlation_id, field_name="correlation_id"),
        )
        object.__setattr__(self, "occurred_at", as_utc(self.occurred_at))
        object.__setattr__(self, "changes", freeze_json_mapping(self.changes))

    def __deepcopy__(self, memo: dict[int, object]) -> AuditEntry:
        """Immutable entries can safely be shared across MemoryStore snapshots."""

        del memo
        return self

    def to_dict(self) -> dict[str, object]:
        """Serialize one audit entry to JSON-compatible primitives."""

        return {
            "id": str(self.id),
            "actor_id": self.actor_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "occurred_at": self.occurred_at.isoformat(),
            "changes": thaw_json_mapping(self.changes),
            "correlation_id": self.correlation_id,
        }
