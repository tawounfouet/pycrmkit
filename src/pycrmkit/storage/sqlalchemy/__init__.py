"""Optional SQLAlchemy persistence adapter and repository implementations."""

from pycrmkit.storage.sqlalchemy.base import (
    NAMING_CONVENTION,
    Base,
    TimestampedModelMixin,
    metadata,
)
from pycrmkit.storage.sqlalchemy.mapping import FunctionalMapper, SQLAlchemyMapper
from pycrmkit.storage.sqlalchemy.models import *  # noqa: F403
from pycrmkit.storage.sqlalchemy.models import __all__ as _models_all
from pycrmkit.storage.sqlalchemy.repositories import *  # noqa: F403
from pycrmkit.storage.sqlalchemy.repositories import __all__ as _repositories_all
from pycrmkit.storage.sqlalchemy.unit_of_work import SessionFactory, SQLAlchemyUnitOfWork

__all__ = [
    "Base",
    "FunctionalMapper",
    "NAMING_CONVENTION",
    "SQLAlchemyMapper",
    "SessionFactory",
    "SQLAlchemyUnitOfWork",
    "TimestampedModelMixin",
    "metadata",
    *_models_all,
    *_repositories_all,
]
