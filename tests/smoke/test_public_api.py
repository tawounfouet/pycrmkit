"""Stable public API freeze for PyCRMKit 0.1."""

import pycrmkit
from pycrmkit import CRM, CRMConfig, CRMContext, __version__


def test_shallow_public_imports() -> None:
    assert CRM.__name__ == "CRM"
    assert CRMConfig.__name__ == "CRMConfig"
    assert CRMContext.__name__ == "CRMContext"
    assert __version__ == "0.1.0"


def test_root_public_exports_are_frozen() -> None:
    assert pycrmkit.__all__ == ["CRM", "CRMConfig", "CRMContext", "__version__"]


def test_stable_facade_namespaces_are_available() -> None:
    crm = CRM.memory()
    assert crm.contacts is not None
    assert crm.organizations is not None
    assert crm.relationships is not None
    assert crm.tags is not None
    assert crm.custom_fields is not None
    assert crm.events is not None
    assert crm.audit is not None
