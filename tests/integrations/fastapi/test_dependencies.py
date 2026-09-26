"""FastAPI dependency bridge qualification."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from pycrmkit import CRM, CRMConfig
from pycrmkit.integrations.fastapi import CRMDependency


def _app() -> FastAPI:
    base = CRM.memory(
        config=CRMConfig(
            default_actor_id="system",
            default_correlation_id="default-correlation",
        )
    )
    dependency = CRMDependency(lambda: base)
    app = FastAPI()

    @app.get("/context")
    def read_context(
        crm: Annotated[CRM, Depends(dependency)],
    ) -> dict[str, str | None]:
        return {
            "actor_id": crm.context.actor_id,
            "correlation_id": crm.context.correlation_id,
        }

    return app


def test_dependency_preserves_default_context_without_headers() -> None:
    response = TestClient(_app()).get("/context")

    assert response.status_code == 200
    assert response.json() == {
        "actor_id": "system",
        "correlation_id": "default-correlation",
    }


def test_dependency_overrides_only_supplied_request_context_headers() -> None:
    client = TestClient(_app())

    actor = client.get("/context", headers={"X-Actor-ID": "api-user"})
    correlation = client.get(
        "/context",
        headers={"X-Correlation-ID": "request-123"},
    )
    both = client.get(
        "/context",
        headers={
            "X-Actor-ID": "api-user",
            "X-Correlation-ID": "request-456",
        },
    )

    assert actor.json() == {
        "actor_id": "api-user",
        "correlation_id": "default-correlation",
    }
    assert correlation.json() == {
        "actor_id": "system",
        "correlation_id": "request-123",
    }
    assert both.json() == {
        "actor_id": "api-user",
        "correlation_id": "request-456",
    }
