"""SQLAlchemy AuditRepository implementation."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from pycrmkit.audit import AuditEntry, AuditEntryId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.sqlalchemy.mappers import audit_from_model, audit_to_model
from pycrmkit.storage.sqlalchemy.models.audit import AuditEntryModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyAuditRepository:
    """Append-only SQLAlchemy audit history adapter."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entry_id: AuditEntryId) -> AuditEntry:
        entry = self.find(entry_id)
        if entry is None:
            raise NotFoundError(
                "Audit entry not found",
                code="audit.not_found",
                context={"audit_entry_id": str(entry_id)},
            )
        return entry

    def find(self, entry_id: AuditEntryId) -> AuditEntry | None:
        model = self.session.get(
            AuditEntryModel,
            str(entry_id),
        )
        return None if model is None else audit_from_model(model)

    def append(self, entry: AuditEntry) -> None:
        if (
            self.session.get(
                AuditEntryModel,
                str(entry.id),
            )
            is not None
        ):
            raise DuplicateError(
                "Audit entry already exists",
                code="audit.duplicate",
                context={"audit_entry_id": str(entry.id)},
            )
        self.session.add(audit_to_model(entry))

    def list_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        page: OffsetPageRequest,
    ) -> Page[AuditEntry]:
        statement = select(AuditEntryModel).where(
            AuditEntryModel.entity_type
            == entity_type.strip().casefold(),
            AuditEntryModel.entity_id == entity_id.strip(),
        )
        return self._page(statement, page)

    def list_by_actor(
        self,
        actor_id: str,
        page: OffsetPageRequest,
    ) -> Page[AuditEntry]:
        return self._page(
            select(AuditEntryModel).where(
                AuditEntryModel.actor_id == actor_id.strip()
            ),
            page,
        )

    def list_by_correlation(
        self,
        correlation_id: str,
        page: OffsetPageRequest,
    ) -> Page[AuditEntry]:
        return self._page(
            select(AuditEntryModel).where(
                AuditEntryModel.correlation_id
                == correlation_id.strip()
            ),
            page,
        )

    def _page(
        self,
        statement: Select[tuple[AuditEntryModel]],
        page: OffsetPageRequest,
    ) -> Page[AuditEntry]:
        ordered = statement.order_by(
            AuditEntryModel.occurred_at.asc(),
            AuditEntryModel.id.asc(),
        )
        return page_models(
            self.session,
            ordered,
            page,
            audit_from_model,
        )
