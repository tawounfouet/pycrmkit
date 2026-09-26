"""FastAPI pagination bridge qualification."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from pycrmkit.core.pagination import Page
from pycrmkit.integrations.fastapi import PageResponse, PaginationParams, pagination_params


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/page")
    def read_page(
        params: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> dict[str, int]:
        page = params.to_domain()
        return {"limit": page.limit, "offset": page.offset}

    return app


def test_pagination_dependency_uses_domain_defaults_and_bounds() -> None:
    client = TestClient(_app())

    default = client.get("/page")
    explicit = client.get("/page?limit=25&offset=50")
    invalid = client.get("/page?limit=201")

    assert default.status_code == 200
    assert default.json() == {"limit": 50, "offset": 0}
    assert explicit.json() == {"limit": 25, "offset": 50}
    assert invalid.status_code == 422


def test_page_response_maps_domain_page_without_losing_metadata() -> None:
    page = Page(items=("a", "b"), limit=2, offset=2, total=5)

    response = PageResponse[str].from_page(page, str.upper)

    assert response.model_dump() == {
        "items": ["A", "B"],
        "limit": 2,
        "offset": 2,
        "total": 5,
        "has_next": True,
        "has_previous": True,
    }
