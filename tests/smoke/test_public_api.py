"""Stable public API freeze for PyCRMKit 0.2."""

import pycrmkit
from pycrmkit import CRM, CRMConfig, CRMContext, __version__


def test_shallow_public_imports() -> None:
    assert CRM.__name__ == "CRM"
    assert CRMConfig.__name__ == "CRMConfig"
    assert CRMContext.__name__ == "CRMContext"
    assert __version__ == "0.2.0"


def test_root_public_exports_remain_0_1_compatible() -> None:
    assert pycrmkit.__all__ == ["CRM", "CRMConfig", "CRMContext", "__version__"]


def test_0_1_facade_namespaces_remain_available() -> None:
    crm = CRM.memory()
    assert crm.contacts is not None
    assert crm.organizations is not None
    assert crm.relationships is not None
    assert crm.tags is not None
    assert crm.custom_fields is not None
    assert crm.events is not None
    assert crm.audit is not None


def test_0_2_stable_namespaces_are_available() -> None:
    crm = CRM.memory()
    assert crm.activities is not None
    assert crm.tasks is not None
    assert crm.timeline is not None


def test_0_2_timeline_namespace_is_read_only_by_surface() -> None:
    crm = CRM.memory()
    assert hasattr(crm.timeline, "get")
    assert hasattr(crm.timeline, "for_contact")
    assert hasattr(crm.timeline, "for_organization")
    assert not hasattr(crm.timeline, "append")
    assert not hasattr(crm.timeline, "delete")
