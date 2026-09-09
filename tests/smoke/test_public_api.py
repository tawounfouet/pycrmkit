"""Compatibility smoke for PyCRMKit 0.3.0a2."""

import pycrmkit
from pycrmkit import CRM, CRMConfig, CRMContext, __version__


def test_shallow_public_imports() -> None:
    assert CRM.__name__ == "CRM"
    assert CRMConfig.__name__ == "CRMConfig"
    assert CRMContext.__name__ == "CRMContext"
    assert __version__ == "0.3.0a2"


def test_root_public_exports_remain_0_1_compatible() -> None:
    assert pycrmkit.__all__ == ["CRM", "CRMConfig", "CRMContext", "__version__"]


def test_stable_and_prior_alpha_namespaces_remain_available() -> None:
    crm = CRM.memory()
    for name in (
        "contacts",
        "organizations",
        "relationships",
        "tags",
        "custom_fields",
        "events",
        "audit",
        "activities",
        "tasks",
        "timeline",
        "leads",
    ):
        assert getattr(crm, name) is not None


def test_lead_facade_remains_deliberately_narrow() -> None:
    crm = CRM.memory()
    assert hasattr(crm.leads, "create")
    assert hasattr(crm.leads, "qualify")
    assert hasattr(crm.leads, "disqualify")
    assert not hasattr(crm.leads, "convert")


def test_0_3_0a2_opportunity_facade_is_creation_only() -> None:
    crm = CRM.memory()
    assert hasattr(crm.opportunities, "create")
    assert not hasattr(crm.opportunities, "move")
    assert not hasattr(crm.opportunities, "mark_won")
    assert not hasattr(crm.opportunities, "mark_lost")
    assert not hasattr(crm.opportunities, "get")
    assert not hasattr(crm.opportunities, "list")
