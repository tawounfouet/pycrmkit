"""Reference FastAPI application backed by PyCRMKit SQLAlchemy/PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit import CRM, __version__
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import InProcessEventBus
from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers
from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork

DATABASE_ENV = "PYCRMKIT_DATABASE_URL"


@dataclass(slots=True)
class ApplicationResources:
    """Resources owned by one reference application instance."""

    engine: Engine
    session_factory: sessionmaker[Session]
    event_bus: InProcessEventBus
    crm: CRM

    def dispose(self) -> None:
        """Release database connection-pool resources."""

        self.engine.dispose()


def build_resources(database_url: str) -> ApplicationResources:
    """Build the PostgreSQL-backed CRM runtime used by the example application."""

    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    event_bus = InProcessEventBus()

    def uow_factory() -> UnitOfWork:
        return SQLAlchemyUnitOfWork(
            session_factory,
            event_publisher=event_bus,
        )

    crm = CRM(
        uow_factory=uow_factory,
        event_bus=event_bus,
        webhook_auto_delivery=False,
    )

    return ApplicationResources(
        engine=engine,
        session_factory=session_factory,
        event_bus=event_bus,
        crm=crm,
    )


def create_app(database_url: str | None = None) -> FastAPI:
    """Create the reference FastAPI application.

    Database schema migrations are intentionally not executed here. Run
    pycrmkit-migrate upgrade head as an explicit deployment step before
    starting the application.
    """

    resolved_database_url = database_url or os.environ.get(DATABASE_ENV)
    if not resolved_database_url:
        raise RuntimeError(
            f"Set {DATABASE_ENV} before creating the FastAPI PostgreSQL example"
        )

    resources = build_resources(resolved_database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        with resources.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        try:
            yield
        finally:
            resources.dispose()

    app = FastAPI(
        title="PyCRMKit FastAPI + PostgreSQL Example",
        version=__version__,
        lifespan=lifespan,
    )
    install_error_handlers(app)
    app.include_router(
        create_crm_router(lambda: resources.crm),
        prefix="/crm",
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        with resources.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "postgresql",
        }

    app.state.pycrmkit_resources = resources
    return app


__all__ = [
    "ApplicationResources",
    "DATABASE_ENV",
    "build_resources",
    "create_app",
]
