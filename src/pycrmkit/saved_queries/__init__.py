"""SavedQuery domain public API."""

from pycrmkit.saved_queries.dto import UNSET, SavedQueryRevision, UnsetType
from pycrmkit.saved_queries.entities import SavedQuery, SavedQueryId, normalize_saved_query_key
from pycrmkit.saved_queries.enums import SavedQueryStatus, SavedQueryVisibility
from pycrmkit.saved_queries.queries import SavedQueryQuery
from pycrmkit.saved_queries.repository import SavedQueryRepository
from pycrmkit.saved_queries.services import SavedQueryService
from pycrmkit.saved_queries.unit_of_work import SavedQueryUnitOfWork

__all__ = [
    "UNSET",
    "SavedQuery",
    "SavedQueryId",
    "SavedQueryQuery",
    "SavedQueryRepository",
    "SavedQueryRevision",
    "SavedQueryService",
    "SavedQueryStatus",
    "SavedQueryUnitOfWork",
    "SavedQueryVisibility",
    "UnsetType",
    "normalize_saved_query_key",
]
