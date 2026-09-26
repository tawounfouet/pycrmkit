"""Installed-wheel FastAPI + PostgreSQL stable smoke."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from examples.fastapi_postgres.app import create_app
from pycrmkit import __version__


def main() -> None:
    database_url = os.environ["PYCRMKIT_TEST_POSTGRES_URL"]
    app = create_app(database_url)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

        created = client.post(
            "/crm/contacts",
            json={"display_name": "Installed Wheel API"},
        )
        assert created.status_code == 201
        contact = created.json()

        fetched = client.get(f"/crm/contacts/{contact['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["display_name"] == "Installed Wheel API"

        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        schema_document = schema.json()
        assert schema_document["info"]["version"] == __version__
        assert "/crm/contacts/{contact_id}" in schema_document["paths"]

    print(f"PyCRMKit {__version__} installed-wheel FastAPI PostgreSQL smoke: OK")


if __name__ == "__main__":
    main()
