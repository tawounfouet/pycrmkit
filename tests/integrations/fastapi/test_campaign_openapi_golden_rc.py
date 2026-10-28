"""LOT-31-003 - Reviewed FastAPI Campaign OpenAPI golden contract.

The fixture is an explicit reviewed b3 contract, not regenerated in the test.
Only /crm/campaigns operations are scoped, leaving unrelated host routes free.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from pycrmkit import CRM
from pycrmkit.integrations.campaign_security import CampaignSecurityBoundary
from pycrmkit.integrations.fastapi import create_crm_router
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess

GOLDEN = Path(__file__).parents[2] / "contracts/campaign_http/openapi_golden_v1_2.json"


def _schema() -> dict[str, Any]:
    crm = CRM.memory(webhook_auto_delivery=False)
    deny_all = CampaignSecurityBoundary(
        lambda _request: None,
        lambda _principal, *, action, campaign_id, scope: False,
    )
    app = FastAPI(title="PyCRMKit 1.2 Campaign contract reference")
    app.include_router(
        create_crm_router(
            lambda: crm,
            campaign_access=CampaignHTTPAccess(lambda: crm, deny_all),
        ),
        prefix="/crm",
    )
    return app.openapi()


def _shape(schema: dict[str, Any], declared: str) -> None:
    category, target = declared.split(":", 1)
    if category == "ref":
        assert schema["$ref"].rsplit("/", 1)[-1] == target
    elif category == "page":
        ref = schema["$ref"].rsplit("/", 1)[-1]
        assert ref.startswith("PageResponse_") and target in ref, ref
    elif category == "array":
        assert schema["type"] == "array"
        assert schema["items"]["$ref"].rsplit("/", 1)[-1] == target
    elif category == "mapping":
        assert schema["type"] == "object"
        assert schema["additionalProperties"]["type"] == target
    else:
        raise AssertionError(f"unsupported golden shape: {declared}")


def test_campaign_opt_in_openapi_operations_and_statuses_are_frozen() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert golden["source_release"] == "1.2.0b3"
    assert golden["target_release"] == "1.2.0rc1"
    actual = _schema()
    paths = {
        name: {method: data for method, data in operations.items()
               if method in {"get", "post", "patch", "put", "delete"}}
        for name, operations in actual["paths"].items()
        if name == "/crm/campaigns" or name.startswith("/crm/campaigns/")
    }
    assert set(paths) == set(golden["operations"])

    for path, expected_methods in golden["operations"].items():
        assert set(paths[path]) == set(expected_methods), path
        for method, expected in expected_methods.items():
            operation = paths[path][method]
            responses = operation["responses"]
            assert sorted(responses, key=int) == expected["response_statuses"], (
                path, method, sorted(responses, key=int),
            )
            response = responses[expected["success_status"]]
            _shape(response["content"]["application/json"]["schema"], expected["response_shape"])
            body = operation.get("requestBody")
            if "request_schema" in expected:
                assert body is not None, (method, path)
                ref = body["content"]["application/json"]["schema"]["$ref"]
                assert ref.rsplit("/", 1)[-1] == expected["request_schema"]
                assert body.get("required") is True
            else:
                assert body is None, (method, path)


def test_campaign_openapi_retains_known_pydantic_components() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    schema = _schema()
    components = schema["components"]["schemas"]
    for operations in golden["operations"].values():
        for operation in operations.values():
            if name := operation.get("request_schema"):
                assert name in components
                assert components[name]["type"] == "object"
    assert "CampaignResponse" in components
    assert {
        "id", "key", "name", "description", "status",
        "created_at", "updated_at", "revision", "metadata", "archived_at",
    }.issubset(components["CampaignResponse"]["properties"])
