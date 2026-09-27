"""Executable compatibility contract for the V1 public API freeze candidate."""

from __future__ import annotations

import importlib
import json
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path

import pycrmkit
from pycrmkit import CRM, CRMConfig, CRMContext
from pycrmkit.core import FixedClock, UUID4Factory
from pycrmkit.events import (
    BUILTIN_EVENT_TYPES,
    DomainEvent,
    EventSerializer,
    default_event_registry,
)
from pycrmkit.exceptions import PyCRMKitError

MANIFEST_PATH = Path(__file__).with_name("public_api_v1_candidate.json")
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _public_callables(value: object) -> list[str]:
    return sorted(
        name
        for name in dir(value)
        if not name.startswith("_") and callable(getattr(value, name))
    )


def test_candidate_version_and_root_exports_are_frozen() -> None:
    assert pycrmkit.__version__ == "1.0.0b1"
    assert pycrmkit.__all__ == MANIFEST["root_exports"]


def test_bounded_context_package_exports_match_manifest() -> None:
    for module_name, expected in MANIFEST["module_exports"].items():
        module = importlib.import_module(module_name)
        assert list(module.__all__) == expected, module_name


def test_public_exception_hierarchy_exports_match_manifest() -> None:
    module = importlib.import_module("pycrmkit.exceptions")
    assert list(module.__all__) == MANIFEST["exceptions"]
    for name in MANIFEST["exceptions"]:
        exported = getattr(module, name)
        assert issubclass(exported, PyCRMKitError) or exported is PyCRMKitError


def test_repository_and_unit_of_work_protocols_remain_importable() -> None:
    symbols = {
        "ActivityRepository": "pycrmkit.activities",
        "AuditRepository": "pycrmkit.audit",
        "CommunicationRepository": "pycrmkit.communication.repository",
        "ContactRepository": "pycrmkit.contacts",
        "CustomFieldRepository": "pycrmkit.custom_fields",
        "ExternalIdentityRepository": "pycrmkit.external_identities",
        "LeadRepository": "pycrmkit.leads",
        "OpportunityRepository": "pycrmkit.opportunities",
        "OrganizationRepository": "pycrmkit.organizations",
        "PipelineRepository": "pycrmkit.pipelines",
        "RelationshipRepository": "pycrmkit.relationships",
        "TagRepository": "pycrmkit.tags",
        "TaskRepository": "pycrmkit.tasks",
        "TimelineRepository": "pycrmkit.timeline",
        "WebhookDeliveryRepository": "pycrmkit.webhooks",
        "WebhookSubscriptionRepository": "pycrmkit.webhooks",
        "UnitOfWork": "pycrmkit.core.unit_of_work",
    }
    assert list(symbols) == MANIFEST["repository_protocols"]
    for symbol, module_name in symbols.items():
        assert getattr(importlib.import_module(module_name), symbol).__name__ == symbol


def test_crm_facade_namespaces_and_methods_match_candidate() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)

    for method in MANIFEST["facade"]["methods"]:
        assert callable(getattr(CRM, method))
    for name in MANIFEST["facade"]["properties"]:
        assert isinstance(getattr(CRM, name), property)

    for namespace, expected_methods in MANIFEST["facade"]["namespaces"].items():
        api = getattr(crm, namespace)
        assert _public_callables(api) == expected_methods, namespace


def test_configuration_shape_is_candidate_frozen() -> None:
    assert [field.name for field in fields(CRMConfig)] == MANIFEST["config_fields"][
        "CRMConfig"
    ]
    assert [field.name for field in fields(CRMContext)] == MANIFEST["config_fields"][
        "CRMContext"
    ]


def test_event_registry_names_and_envelope_shape_are_frozen() -> None:
    assert list(BUILTIN_EVENT_TYPES) == MANIFEST["builtin_event_types"]
    assert [field.name for field in fields(DomainEvent)] == MANIFEST[
        "event_envelope_fields"
    ]

    event = DomainEvent.create(
        id_factory=UUID4Factory(),
        clock=FixedClock(datetime(2026, 9, 27, 10, tzinfo=UTC)),
        type="contact.created",
        aggregate_type="contact",
        aggregate_id="candidate-freeze",
        payload={"fields": ["display_name"]},
    )
    serialized = EventSerializer(default_event_registry()).to_dict(event)
    assert list(serialized) == MANIFEST["event_envelope_fields"]
    assert DomainEvent.from_dict(serialized) == event


def test_documented_external_identity_event_names_are_emitted() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    emitted: list[str] = []

    for event_type in MANIFEST["additional_documented_events"]:
        crm.events.subscribe(
            event_type,
            lambda event, emitted=emitted: emitted.append(str(event.type)),
        )

    contact = crm.contacts.create(display_name="Freeze Candidate")
    crm.external_identities.attach(
        contact,
        system="candidate",
        external_id="contact-001",
    )
    crm.external_identities.detach("candidate", "contact-001")

    assert emitted == MANIFEST["additional_documented_events"]


def test_classification_buckets_are_explicit_and_non_overlapping() -> None:
    public_adapter_entrypoints = set(MANIFEST["public_adapter_entrypoints"])
    provisional = set(MANIFEST["provisional"])
    internal = set(MANIFEST["internal"])

    assert public_adapter_entrypoints
    assert provisional
    assert internal
    assert public_adapter_entrypoints.isdisjoint(provisional)
    assert public_adapter_entrypoints.isdisjoint(internal)
    assert provisional.isdisjoint(internal)
    assert MANIFEST["audit_actions"] == ["contact.merged"]
