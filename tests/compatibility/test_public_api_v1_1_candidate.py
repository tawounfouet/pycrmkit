"""Executable compatibility contract for the PyCRMKit 1.1 public API candidate."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pycrmkit
from pycrmkit import CRM
from pycrmkit.events import BUILTIN_EVENT_TYPES

MANIFEST_PATH = Path(__file__).with_name("public_api_v1_1_candidate.json")
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _public_callables(value: object) -> list[str]:
    return sorted(
        name
        for name in dir(value)
        if not name.startswith("_") and callable(getattr(value, name))
    )


def test_v1_1_candidate_version_is_frozen() -> None:
    assert MANIFEST["target_release"] == "1.1.0rc1"
    assert MANIFEST["baseline_release"] == "1.1.0b3"
    assert pycrmkit.__version__ in {
        MANIFEST["target_release"],
        MANIFEST["promoted_release"],
    }


def test_v1_1_module_exports_are_exactly_frozen() -> None:
    for module_name, expected in MANIFEST["module_exports"].items():
        module = importlib.import_module(module_name)
        assert list(module.__all__) == expected, module_name


def test_v1_1_repository_protocols_remain_importable() -> None:
    symbols = {
        "SavedQueryRepository": "pycrmkit.saved_queries",
        "SavedQueryUnitOfWork": "pycrmkit.saved_queries",
        "SegmentRepository": "pycrmkit.segments",
        "SegmentMembershipRepository": "pycrmkit.segments",
        "SegmentQueryExecutor": "pycrmkit.segments",
        "SegmentUnitOfWork": "pycrmkit.segments",
    }
    assert list(symbols) == MANIFEST["repository_protocols"]
    for symbol, module_name in symbols.items():
        assert getattr(importlib.import_module(module_name), symbol).__name__ == symbol


def test_v1_1_facade_namespaces_are_candidate_final() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    for namespace, expected in MANIFEST["facade_namespaces"].items():
        assert _public_callables(getattr(crm, namespace)) == sorted(expected)


def test_v1_1_segmentation_events_are_registered_contracts() -> None:
    assert set(MANIFEST["event_types"]).issubset(BUILTIN_EVENT_TYPES)


def test_v1_1_freeze_extends_v1_instead_of_replacing_it() -> None:
    assert MANIFEST["extends"] == "tests/compatibility/public_api_v1_candidate.json"
    assert MANIFEST["scope_boundary"]
