"""Compatibility smoke for the PyCRMKit 0.3.0rc1 candidate surface."""

import pycrmkit
from pycrmkit import CRM, CRMConfig, CRMContext, __version__


def test_shallow_public_imports() -> None:
    assert CRM.__name__ == "CRM"
    assert CRMConfig.__name__ == "CRMConfig"
    assert CRMContext.__name__ == "CRMContext"
    assert __version__ == "0.3.0rc1"


def test_root_public_exports_remain_0_1_compatible() -> None:
    assert pycrmkit.__all__ == ["CRM", "CRMConfig", "CRMContext", "__version__"]


def test_stable_and_sales_candidate_namespaces_remain_available() -> None:
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
        "opportunities",
        "pipelines",
    ):
        assert getattr(crm, name) is not None


def test_0_3_candidate_lead_facade_surface() -> None:
    crm = CRM.memory()
    assert hasattr(crm.leads, "create")
    assert hasattr(crm.leads, "qualify")
    assert hasattr(crm.leads, "disqualify")
    assert hasattr(crm.leads, "convert")
    assert not hasattr(crm.leads, "get")
    assert not hasattr(crm.leads, "list")


def test_0_3_candidate_opportunity_facade_surface() -> None:
    crm = CRM.memory()
    assert hasattr(crm.opportunities, "create")
    assert hasattr(crm.opportunities, "move")
    assert not hasattr(crm.opportunities, "mark_won")
    assert not hasattr(crm.opportunities, "mark_lost")
    assert not hasattr(crm.opportunities, "get")
    assert not hasattr(crm.opportunities, "list")


def test_0_3_candidate_pipeline_facade_surface() -> None:
    crm = CRM.memory()
    assert hasattr(crm.pipelines, "define")
    assert hasattr(crm.pipelines, "get")
    assert hasattr(crm.pipelines, "list")
