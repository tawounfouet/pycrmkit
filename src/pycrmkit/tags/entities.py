"""Tag and assignment entities."""

from __future__ import annotations

from dataclasses import dataclass, field

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.tags.value_objects import TagName


class TagId(UUIDId):
    """Strongly typed identifier for a Tag."""


class TagAssignmentId(UUIDId):
    """Strongly typed identifier for a Tag assignment."""


@dataclass(eq=False, slots=True)
class Tag(TimestampedEntity[TagId]):
    """Reusable normalized CRM tag."""

    name: TagName
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.metadata = dict(self.metadata)


@dataclass(eq=False, slots=True)
class TagAssignment(TimestampedEntity[TagAssignmentId]):
    """Assignment of one Tag to one CRM entity reference."""

    tag_id: TagId
    entity: EntityReference
