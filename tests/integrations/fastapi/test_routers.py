"""Reusable FastAPI router qualification for PyCRMKit 0.7.0b1."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pycrmkit import CRM
from pycrmkit.integrations.fastapi import create_crm_router


def _client(crm: CRM) -> TestClient:
    app = FastAPI()
    app.include_router(create_crm_router(lambda: crm), prefix="/crm")
    return TestClient(app)


def test_composite_router_exposes_all_v0_7_b1_surfaces() -> None:
    crm = CRM.memory()
    app = FastAPI()
    app.include_router(create_crm_router(lambda: crm), prefix="/crm")

    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert {
        "/crm/contacts",
        "/crm/organizations",
        "/crm/relationships",
        "/crm/activities",
        "/crm/tasks",
        "/crm/leads",
        "/crm/opportunities",
        "/crm/timeline/contacts/{contact_id}",
        "/crm/timeline/organizations/{organization_id}",
    }.issubset(paths)


def test_contact_and_organization_http_lifecycle() -> None:
    client = _client(CRM.memory())

    created_contact = client.post(
        "/crm/contacts",
        json={"first_name": "Ada", "last_name": "Lovelace", "source": "api"},
    )
    assert created_contact.status_code == 201
    contact = created_contact.json()

    listed_contacts = client.get("/crm/contacts?limit=10&offset=0")
    assert listed_contacts.status_code == 200
    assert listed_contacts.json()["total"] == 1
    assert listed_contacts.json()["items"][0]["id"] == contact["id"]

    updated_contact = client.patch(
        f"/crm/contacts/{contact['id']}",
        json={"source": "api-v2"},
    )
    assert updated_contact.status_code == 200
    assert updated_contact.json()["source"] == "api-v2"

    archived_contact = client.post(f"/crm/contacts/{contact['id']}/archive")
    assert archived_contact.status_code == 200
    assert archived_contact.json()["archived_at"] is not None

    created_organization = client.post(
        "/crm/organizations",
        json={"legal_name": "Analytical Engines Ltd"},
    )
    assert created_organization.status_code == 201
    organization = created_organization.json()

    fetched = client.get(f"/crm/organizations/{organization['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["legal_name"] == "Analytical Engines Ltd"

    listed = client.get("/crm/organizations")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_relationship_activity_task_and_timeline_routes_compose() -> None:
    client = _client(CRM.memory())

    contact = client.post(
        "/crm/contacts",
        json={"display_name": "Ada"},
    ).json()
    organization = client.post(
        "/crm/organizations",
        json={"legal_name": "Analytical Engines"},
    ).json()

    relationship = client.post(
        "/crm/relationships",
        json={
            "source": {"kind": "contact", "id": contact["id"]},
            "target": {"kind": "organization", "id": organization["id"]},
            "relationship_type": "employment",
            "role": "founder",
        },
    )
    assert relationship.status_code == 201

    ended = client.post(
        f"/crm/relationships/{relationship.json()['id']}/end",
    )
    assert ended.status_code == 200
    assert ended.json()["is_ended"] is True

    activity = client.post(
        "/crm/activities",
        json={
            "type": "meeting",
            "subject": "Architecture review",
            "participants": [
                {
                    "reference": {"kind": "contact", "id": contact["id"]},
                    "role": "customer",
                    "is_primary": True,
                }
            ],
        },
    )
    assert activity.status_code == 201

    task = client.post(
        "/crm/tasks",
        json={
            "title": "Prepare proposal",
            "priority": "high",
            "references": [{"kind": "contact", "id": contact["id"]}],
        },
    )
    assert task.status_code == 201
    task_id = task.json()["id"]

    started = client.post(f"/crm/tasks/{task_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    completed = client.post(f"/crm/tasks/{task_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    timeline = client.get(f"/crm/timeline/contacts/{contact['id']}")
    assert timeline.status_code == 200
    event_types = {item["event_type"] for item in timeline.json()["items"]}
    assert {"activity.created", "task.created"}.issubset(event_types)
