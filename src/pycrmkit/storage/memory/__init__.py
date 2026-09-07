"""Official in-memory persistence adapter for PyCRMKit."""

from pycrmkit.storage.memory._state import MemoryStore
from pycrmkit.storage.memory.activities import MemoryActivityRepository
from pycrmkit.storage.memory.audit import MemoryAuditRepository
from pycrmkit.storage.memory.contacts import MemoryContactRepository
from pycrmkit.storage.memory.custom_fields import MemoryCustomFieldRepository
from pycrmkit.storage.memory.organizations import MemoryOrganizationRepository
from pycrmkit.storage.memory.relationships import MemoryRelationshipRepository
from pycrmkit.storage.memory.tags import MemoryTagRepository
from pycrmkit.storage.memory.tasks import MemoryTaskRepository
from pycrmkit.storage.memory.timeline import MemoryTimelineRepository
from pycrmkit.storage.memory.unit_of_work import MemoryUnitOfWork

__all__ = [
    "MemoryActivityRepository",
    "MemoryAuditRepository",
    "MemoryContactRepository",
    "MemoryCustomFieldRepository",
    "MemoryOrganizationRepository",
    "MemoryRelationshipRepository",
    "MemoryStore",
    "MemoryTaskRepository",
    "MemoryTimelineRepository",
    "MemoryTagRepository",
    "MemoryUnitOfWork",
]
