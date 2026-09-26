"""PostgreSQL-backed FastAPI release-candidate E2E qualification."""

from __future__ import annotations

import os

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from pycrmkit.storage.sqlalchemy.migrations.cli import migration_config

DATABASE_ENV = "PYCRMKIT_TEST_POSTGRES_URL"


def _reset_and_migrate(database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")
    engine.dispose()
    command.upgrade(migration_config(database_url), "head")


@pytest.mark.postgresql
def test_reference_fastapi_application_persists_http_journey_across_restart() -> None:
    database_url = os.environ.get(DATABASE_ENV)
    if not database_url:
        pytest.skip(f"{DATABASE_ENV} is required for FastAPI PostgreSQL E2E")

    from examples.fastapi_postgres.app import create_app

    _reset_and_migrate(database_url)

    app = create_app(database_url)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "database": "postgresql"}

        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        assert "/crm/contacts" in openapi.json()["paths"]

        contact_response = client.post(
            "/crm/contacts",
            json={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "source": "postgres-e2e",
            },
            headers={
                "X-Actor-ID": "api-e2e",
                "X-Correlation-ID": "fastapi-postgres-e2e",
            },
        )
        assert contact_response.status_code == 201
        contact = contact_response.json()

        organization_response = client.post(
            "/crm/organizations",
            json={"legal_name": "Analytical Engines Ltd"},
        )
        assert organization_response.status_code == 201
        organization = organization_response.json()

        relationship_response = client.post(
            "/crm/relationships",
            json={
                "source": {"kind": "contact", "id": contact["id"]},
                "target": {"kind": "organization", "id": organization["id"]},
                "relationship_type": "employment",
                "role": "founder",
            },
        )
        assert relationship_response.status_code == 201

        activity_response = client.post(
            "/crm/activities",
            json={
                "type": "meeting",
                "subject": "PostgreSQL API review",
                "participants": [
                    {
                        "reference": {"kind": "contact", "id": contact["id"]},
                        "role": "customer",
                        "is_primary": True,
                    }
                ],
            },
        )
        assert activity_response.status_code == 201

        task_response = client.post(
            "/crm/tasks",
            json={
                "title": "Prepare PostgreSQL proposal",
                "priority": "high",
                "references": [{"kind": "contact", "id": contact["id"]}],
            },
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["id"]

        completed = client.post(f"/crm/tasks/{task_id}/complete")
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"

        timeline = client.get(f"/crm/timeline/contacts/{contact['id']}")
        assert timeline.status_code == 200
        event_types = {item["event_type"] for item in timeline.json()["items"]}
        assert {"activity.created", "task.created", "task.completed"}.issubset(event_types)

        missing_id = "00000000-0000-4000-8000-000000000001"
        missing = client.get(f"/crm/contacts/{missing_id}")
        assert missing.status_code == 404
        assert missing.json()["code"] == "contact.not_found"

    restarted_app = create_app(database_url)
    with TestClient(restarted_app) as restarted_client:
        persisted = restarted_client.get(f"/crm/contacts/{contact['id']}")
        assert persisted.status_code == 200
        assert persisted.json()["display_name"] == "Ada Lovelace"

        organizations = restarted_client.get("/crm/organizations")
        assert organizations.status_code == 200
        assert organizations.json()["total"] == 1
