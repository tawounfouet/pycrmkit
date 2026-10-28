"""Executable PyCRMKit 1.2 Campaign API freeze; extends V1 and V1.1.

Core checks run without optional transports. The two optional-schema checks
skip only when the corresponding extra is not installed. The public-api
workflow runs the full suite and also exercises the manifest from a wheel.
"""

from __future__ import annotations

import importlib
import inspect
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from pycrmkit import CRM
from pycrmkit import campaigns as campaign_api
from pycrmkit.campaigns import UNSET, CampaignQuery, CampaignStatus, CampaignUpdate
from pycrmkit.events import BUILTIN_EVENT_TYPES, default_event_registry
from pycrmkit.exceptions import PyCRMKitError, ValidationError

MANIFEST_PATH = Path(__file__).with_name("public_api_v1_2_campaign_candidate.json")
MANIFEST: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _default_token(value: Any) -> str:
    if value is inspect.Parameter.empty:
        return "<required>"
    if value is None:
        return "None"
    if type(value) is bool:
        return f"bool:{value}"
    if type(value) is int:
        return f"int:{value}"
    if type(value) is str:
        return f"str:{value}"
    raise AssertionError(f"unexpected public signature default: {type(value).__name__}")


def _annotation(value: Any) -> str:
    if value is inspect.Signature.empty:
        return "<missing>"
    return str(value)


def _signature(value: Any) -> dict[str, Any]:
    signature = inspect.signature(value)
    return {
        "parameters": [
            {
                "name": param.name,
                "kind": param.kind.name,
                "annotation": _annotation(param.annotation),
                "default": _default_token(param.default),
            }
            for param in signature.parameters.values()
        ],
        "returns": _annotation(signature.return_annotation),
    }


def _public_methods(value: Any) -> list[str]:
    return sorted(
        name
        for name in dir(value)
        if not name.startswith("_") and callable(getattr(value, name))
    )


def test_1_2_freeze_extends_unchanged_older_manifests() -> None:
    assert MANIFEST["schema_version"] == 1
    assert MANIFEST["baseline_release"] == "1.2.0b3"
    assert MANIFEST["target_release"] == "1.2.0rc1"
    assert MANIFEST["promoted_release"] == "1.2.0"
    expected = [
        "tests/compatibility/public_api_v1_candidate.json",
        "tests/compatibility/public_api_v1_1_candidate.json",
    ]
    assert MANIFEST["extends"] == expected
    for relpath in expected:
        assert (MANIFEST_PATH.parent / Path(relpath).name).is_file()


def test_campaign_exports_are_importable_and_exact() -> None:
    for module_name, expected in MANIFEST["module_exports"].items():
        module = importlib.import_module(module_name)
        assert list(module.__all__) == expected
        for symbol in expected:
            assert getattr(module, symbol) is not None, (module_name, symbol)


def test_campaign_facade_method_names_and_full_signatures_are_frozen() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    namespace = getattr(crm, MANIFEST["facade_namespace"])
    expected: dict[str, Any] = MANIFEST["facade_signatures"]
    assert _public_methods(namespace) == sorted(expected)
    for method_name, baseline in expected.items():
        assert _signature(getattr(namespace, method_name)) == baseline, method_name


def test_campaign_python_dataops_full_signatures_are_frozen() -> None:
    for name, expected in MANIFEST["dataops_signatures"].items():
        assert _signature(getattr(campaign_api, name)) == expected, name


def test_campaign_domain_local_fields_are_frozen() -> None:
    for name, expected in MANIFEST["domain_local_fields"].items():
        domain_type = getattr(campaign_api, name)
        assert list(domain_type.__annotations__) == expected, name
        assert set(expected).issubset({field.name for field in fields(domain_type)})


def test_campaign_status_and_registered_events_are_exact() -> None:
    assert [item.value for item in CampaignStatus] == MANIFEST["campaign_status_values"]
    registered = sorted(name for name in BUILTIN_EVENT_TYPES if name.startswith("campaign."))
    assert registered == MANIFEST["event_types"]
    registry = default_event_registry()
    assert all(registry.supports(name, 1) for name in registered)


def test_update_unset_and_query_semantics_are_frozen() -> None:
    assert [field.name for field in fields(CampaignUpdate)] == MANIFEST["invariants"]["unsets"]
    blank = CampaignUpdate()
    assert all(getattr(blank, name) is UNSET for name in MANIFEST["invariants"]["unsets"])
    updated = CampaignUpdate(description=None)
    assert updated.description is None
    assert updated.name is UNSET
    assert [field.name for field in fields(CampaignQuery)] == MANIFEST[
        "domain_local_fields"
    ]["CampaignQuery"]
    assert campaign_api.MAX_CAMPAIGN_IMPORT_ROWS == MANIFEST["invariants"][
        "max_campaign_import_rows"
    ]
    assert not set(MANIFEST["invariants"]["exclude_patch_fields"]).intersection(
        MANIFEST["invariants"]["unsets"]
    )


def test_public_error_classes_and_campaign_key_error_code() -> None:
    errors = importlib.import_module("pycrmkit.exceptions")
    for name in MANIFEST["exception_names"]:
        value = getattr(errors, name)
        assert issubclass(value, PyCRMKitError)
    assert "campaign.key.invalid" in MANIFEST["domain_error_codes"]
    with pytest.raises(ValidationError) as captured:
        campaign_api.normalize_campaign_key("!!!")
    assert captured.value.code == "campaign.key.invalid"


def test_fastapi_campaign_pydantic_field_contract_when_extra_installed() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("pydantic")
    schemas = importlib.import_module("pycrmkit.integrations.fastapi.campaign_schemas")
    for name, expected in MANIFEST["fastapi_pydantic_fields"].items():
        model = getattr(schemas, name)
        assert list(model.model_fields) == expected["fields"], name
        assert [
            field_name
            for field_name, field in model.model_fields.items()
            if field.is_required()
        ] == expected["required"], name


def test_drf_campaign_serializer_fields_when_extra_installed() -> None:
    pytest.importorskip("django")
    pytest.importorskip("rest_framework")
    from django.conf import settings

    if not settings.configured:
        pytest.skip("DRF schema freeze runs in tests/integrations/drf with configured settings")
    serializers = importlib.import_module(
        "pycrmkit.integrations.django.drf.campaign_serializers"
    )
    for name, expected in MANIFEST["drf_serializer_fields"].items():
        serializer = getattr(serializers, name)
        assert list(serializer._declared_fields) == expected, name
