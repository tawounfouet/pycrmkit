from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pycrmkit import CRM
from pycrmkit.integrations.fastapi import (
    create_crm_router,
    install_error_handlers,
)
from pycrmkit.segments import (
    Predicate,
    QueryOperator,
    expression_to_dict,
)


def _client(crm: CRM) -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(create_crm_router(lambda: crm), prefix="/crm")
    return TestClient(app)


def test_fastapi_saved_query_segment_snapshot_and_bulk_membership_flow() -> None:
    client = _client(CRM.memory(webhook_auto_delivery=False))
    ada = client.post(
        "/crm/contacts",
        json={"display_name": "Ada", "source": "LinkedIn"},
    ).json()
    grace = client.post(
        "/crm/contacts",
        json={"display_name": "Grace", "source": "Newsletter"},
    ).json()

    expression = expression_to_dict(
        Predicate("source", QueryOperator.EQ, "linkedin")
    )
    saved = client.post(
        "/crm/saved-queries",
        json={
            "key": "linkedin",
            "name": "LinkedIn",
            "entity_kind": "contact",
            "expression": expression,
        },
    )
    assert saved.status_code == 201
    saved_id = saved.json()["id"]

    executed = client.get(
        f"/crm/saved-queries/{saved_id}/execute?limit=10&offset=0"
    )
    assert executed.status_code == 200
    assert executed.json()["total"] == 1
    assert executed.json()["items"][0]["id"] == ada["id"]

    dynamic = client.post(
        "/crm/segments",
        json={
            "key": "linkedin-segment",
            "name": "LinkedIn Segment",
            "entity_kind": "contact",
            "mode": "dynamic",
            "expression": expression,
        },
    )
    assert dynamic.status_code == 201
    dynamic_id = dynamic.json()["id"]

    members = client.get(f"/crm/segments/{dynamic_id}/members")
    assert members.status_code == 200
    assert members.json()["items"][0]["id"] == ada["id"]

    snapshot = client.post(
        f"/crm/segments/{dynamic_id}/snapshot",
        json={
            "key": "linkedin-frozen",
            "name": "LinkedIn Frozen",
        },
    )
    assert snapshot.status_code == 201
    assert snapshot.json()["mode"] == "snapshot"

    static = client.post(
        "/crm/segments",
        json={
            "key": "manual-list",
            "name": "Manual List",
            "entity_kind": "contact",
            "mode": "static",
        },
    )
    assert static.status_code == 201
    static_id = static.json()["id"]

    added = client.post(
        f"/crm/segments/{static_id}/members",
        json={
            "members": [
                {"kind": "contact", "id": ada["id"]},
                {"kind": "contact", "id": grace["id"]},
            ],
            "source": "api",
        },
    )
    assert added.status_code == 200
    assert len(added.json()) == 2

    removed = client.post(
        f"/crm/segments/{static_id}/members/remove",
        json={
            "members": [{"kind": "contact", "id": grace["id"]}],
        },
    )
    assert removed.status_code == 200
    assert removed.json() == {"removed": 1}
