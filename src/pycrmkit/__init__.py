"""PyCRMKit public package."""

from pycrmkit.__about__ import __version__
from pycrmkit.config import CRMConfig, CRMContext
from pycrmkit.crm import CRM

__all__ = ["CRM", "CRMConfig", "CRMContext", "__version__"]
