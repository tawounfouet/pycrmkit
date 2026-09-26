"""Optional SQLAlchemy persistence adapter foundation."""

from pycrmkit.storage.sqlalchemy.base import (
    NAMING_CONVENTION,
    Base,
    TimestampedModelMixin,
    metadata,
)
from pycrmkit.storage.sqlalchemy.mapping import FunctionalMapper, SQLAlchemyMapper
from pycrmkit.storage.sqlalchemy.models import *  # noqa: F403
from pycrmkit.storage.sqlalchemy.models import __all__ as _models_all

__all__ = [
    "Base",
    "FunctionalMapper",
    "NAMING_CONVENTION",
    "SQLAlchemyMapper",
    "TimestampedModelMixin",
    "metadata",
    *_models_all,
]
