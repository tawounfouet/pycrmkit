"""FastAPI sales command-router qualification."""

from __future__ import annotations

from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pycrmkit import CRM
from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers
from pycrmkit.pipelines import Stage, StageTransition


def test_lead_conversion_and_opportunity_move_remain_facade_commands() -> None:
    crm = CRM.memory()
    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("won", "Won", 10, terminal=True, outcome="won"),
        ),
        transitions=(StageTransition("new", "won"),),
    )
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(create_crm_router(lambda: crm), prefix="/crm")
    client = TestClient(app)

    contact = client.post(
        "/crm/contacts",
        json={"display_name": "Commercial contact"},
    ).json()

    created_lead = client.post(
        "/crm/leads",
        json={"contact_id": contact["id"], "source": "api"},
    )
    assert created_lead.status_code == 201
    lead = created_lead.json()

    qualified = client.post(f"/crm/leads/{lead['id']}/qualify")
    assert qualified.status_code == 200
    assert qualified.json()["status"] == "qualified"

    converted = client.post(
        f"/crm/leads/{lead['id']}/convert",
        json={
            "name": "API opportunity",
            "estimated_value": "1250.50",
            "currency": "EUR",
            "pipeline_id": "sales",
            "idempotency_key": "router-conversion-1",
        },
    )
    assert converted.status_code == 200
    opportunity = converted.json()
    assert opportunity["contact_id"] == contact["id"]
    assert opportunity["stage_id"] == "new"

    moved = client.post(
        f"/crm/opportunities/{opportunity['id']}/move",
        json={"to": "won"},
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "won"
