"""Compatibility smoke for the stable PyCRMKit 0.5 public surface."""

import pycrmkit
from pycrmkit import CRM, CRMConfig, CRMContext, __version__


def test_shallow_public_imports() -> None:
    assert CRM.__name__ == "CRM"
    assert CRMConfig.__name__ == "CRMConfig"
    assert CRMContext.__name__ == "CRMContext"
    assert __version__ == "1.0.0"


def test_root_public_exports_remain_0_1_compatible() -> None:
    assert pycrmkit.__all__ == ["CRM", "CRMConfig", "CRMContext", "__version__"]


def test_stable_0_3_namespaces_remain_available() -> None:
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
        "email",
        "webhooks",
    ):
        assert getattr(crm, name) is not None


def test_stable_0_3_lead_facade_surface() -> None:
    crm = CRM.memory()
    assert hasattr(crm.leads, "create")
    assert hasattr(crm.leads, "qualify")
    assert hasattr(crm.leads, "disqualify")
    assert hasattr(crm.leads, "convert")
    assert not hasattr(crm.leads, "get")
    assert not hasattr(crm.leads, "list")


def test_stable_0_3_opportunity_facade_surface() -> None:
    crm = CRM.memory()
    assert hasattr(crm.opportunities, "create")
    assert hasattr(crm.opportunities, "move")
    assert not hasattr(crm.opportunities, "mark_won")
    assert not hasattr(crm.opportunities, "mark_lost")
    assert not hasattr(crm.opportunities, "get")
    assert not hasattr(crm.opportunities, "list")


def test_stable_0_3_pipeline_facade_surface() -> None:
    crm = CRM.memory()
    assert hasattr(crm.pipelines, "define")
    assert hasattr(crm.pipelines, "get")
    assert hasattr(crm.pipelines, "list")


def test_stable_0_4_email_facade_surface() -> None:
    crm = CRM.memory()
    for name in (
        "send",
        "record_delivery_event",
        "get",
        "for_contact",
        "for_organization",
        "delivery_history",
    ):
        assert hasattr(crm.email, name)


def test_0_5_causal_context_surface_is_additive() -> None:
    crm = CRM.memory()
    assert hasattr(crm, "with_event")
    assert hasattr(CRMContext, "from_event")


def test_0_9_external_identity_facade_surface() -> None:
    crm = CRM.memory()
    for name in ("attach", "resolve", "list_for_entity", "detach"):
        assert hasattr(crm.external_identities, name)


def test_0_9_import_framework_surface() -> None:
    from pycrmkit.importers import ImportPipeline, ImportReport, IterableReader

    assert ImportPipeline.__name__ == "ImportPipeline"
    assert ImportReport.__name__ == "ImportReport"
    assert IterableReader.__name__ == "IterableReader"


def test_0_9_format_adapter_surface() -> None:
    from pycrmkit.exporters import CSVExporter, JSONExporter, JSONLExporter
    from pycrmkit.importers import CSVReader, JSONLReader, JSONReader

    assert CSVReader.__name__ == "CSVReader"
    assert JSONReader.__name__ == "JSONReader"
    assert JSONLReader.__name__ == "JSONLReader"
    assert CSVExporter.__name__ == "CSVExporter"
    assert JSONExporter.__name__ == "JSONExporter"
    assert JSONLExporter.__name__ == "JSONLExporter"


def test_0_9_deduplication_surface() -> None:
    from pycrmkit.dedup import (
        CandidateRecord,
        DeduplicationEngine,
        DedupScorePolicy,
        InMemoryCandidateSource,
    )

    assert CandidateRecord.__name__ == "CandidateRecord"
    assert DedupScorePolicy.__name__ == "DedupScorePolicy"
    assert DeduplicationEngine.__name__ == "DeduplicationEngine"
    assert InMemoryCandidateSource.__name__ == "InMemoryCandidateSource"


def test_0_9_merge_surface() -> None:
    from pycrmkit.dedup import MergePolicy, MergeResolution, MergeResult, MergeService

    assert MergePolicy.__name__ == "MergePolicy"
    assert MergeResolution.__name__ == "MergeResolution"
    assert MergeResult.__name__ == "MergeResult"
    assert MergeService.__name__ == "MergeService"


def test_0_5_webhook_delivery_surface() -> None:
    crm = CRM.memory()
    for name in (
        "register",
        "disable",
        "list",
        "deliver",
        "retry_due",
        "deliveries",
        "attempts",
    ):
        assert hasattr(crm.webhooks, name)
