"""Tags domain public API."""

from pycrmkit.tags.entities import Tag, TagAssignment, TagAssignmentId, TagId
from pycrmkit.tags.queries import TagQuery
from pycrmkit.tags.repository import TagRepository
from pycrmkit.tags.services import TagService
from pycrmkit.tags.value_objects import TagName

__all__ = [
    "Tag",
    "TagAssignment",
    "TagAssignmentId",
    "TagId",
    "TagName",
    "TagQuery",
    "TagRepository",
    "TagService",
]
