"""SQLAlchemy repository for versioned SavedQuery definitions."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.saved_queries import (
    SavedQuery,
    SavedQueryId,
    SavedQueryQuery,
    SavedQueryStatus,
    normalize_saved_query_key,
)
from pycrmkit.storage.sqlalchemy.models.segmentation import SavedQueryModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models
from pycrmkit.storage.sqlalchemy.segmentation_codec import (
    saved_query_from_model,
    saved_query_to_model,
)


class SQLAlchemySavedQueryRepository:
    """Append-only SavedQuery revision repository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery:
        query = self.find(query_id, revision)
        if query is None:
            raise NotFoundError(
                "Saved query not found",
                code=(
                    "saved_query.not_found"
                    if revision is None
                    else "saved_query.revision.not_found"
                ),
                context={
                    "saved_query_id": str(query_id),
                    "revision": revision,
                },
            )
        return query

    def find(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery | None:
        identifier = str(query_id)
        if revision is None:
            model = self.session.scalar(
                select(SavedQueryModel)
                .where(SavedQueryModel.id == identifier)
                .order_by(SavedQueryModel.revision.desc())
                .limit(1)
            )
        else:
            model = self.session.get(
                SavedQueryModel,
                (identifier, revision),
            )
        return None if model is None else saved_query_from_model(model)

    def find_by_key(self, key: str) -> SavedQuery | None:
        normalized = normalize_saved_query_key(key)
        model = self.session.scalar(
            select(SavedQueryModel)
            .where(SavedQueryModel.key == normalized)
            .order_by(SavedQueryModel.revision.desc())
            .limit(1)
        )
        return None if model is None else saved_query_from_model(model)

    def save(self, query: SavedQuery) -> None:
        existing_by_key = self.find_by_key(query.key)
        current = self.session.scalar(
            select(SavedQueryModel)
            .where(SavedQueryModel.id == str(query.id))
            .order_by(SavedQueryModel.revision.desc())
            .limit(1)
        )

        if (
            existing_by_key is not None
            and existing_by_key.id != query.id
        ):
            raise DuplicateError(
                "Saved-query key already exists",
                code="saved_query.key.duplicate",
                context={"key": query.key},
            )

        expected = 1 if current is None else current.revision + 1
        if query.revision != expected:
            raise ConflictError(
                "Saved-query revisions must be appended sequentially",
                code="saved_query.revision.conflict",
                context={"expected": expected, "actual": query.revision},
            )
        if current is not None and query.key != current.key:
            raise ConflictError(
                "Saved-query key is immutable",
                code="saved_query.key.immutable",
            )
        if current is not None and query.entity_kind != current.entity_kind:
            raise ConflictError(
                "Saved-query entity kind is immutable",
                code="saved_query.entity_kind.immutable",
            )

        self.session.add(saved_query_to_model(query))

    def list_revisions(
        self,
        query_id: SavedQueryId,
    ) -> tuple[SavedQuery, ...]:
        models = self.session.scalars(
            select(SavedQueryModel)
            .where(SavedQueryModel.id == str(query_id))
            .order_by(SavedQueryModel.revision.asc())
        ).all()
        return tuple(saved_query_from_model(model) for model in models)

    def search(
        self,
        query: SavedQueryQuery,
        page: OffsetPageRequest,
    ) -> Page[SavedQuery]:
        latest = (
            select(
                SavedQueryModel.id.label("query_id"),
                func.max(SavedQueryModel.revision).label("max_revision"),
            )
            .group_by(SavedQueryModel.id)
            .subquery()
        )
        statement = select(SavedQueryModel).join(
            latest,
            (SavedQueryModel.id == latest.c.query_id)
            & (SavedQueryModel.revision == latest.c.max_revision),
        )
        if not query.include_archived:
            statement = statement.where(
                SavedQueryModel.status != SavedQueryStatus.ARCHIVED.value
            )
        if query.status is not None:
            statement = statement.where(
                SavedQueryModel.status == query.status.value
            )
        if query.visibility is not None:
            statement = statement.where(
                SavedQueryModel.visibility == query.visibility.value
            )
        if query.entity_kind is not None:
            statement = statement.where(
                SavedQueryModel.entity_kind == query.entity_kind
            )
        if query.owner_id is not None:
            statement = statement.where(
                SavedQueryModel.owner_id == str(query.owner_id)
            )
        statement = statement.order_by(
            func.lower(SavedQueryModel.name).asc(),
            SavedQueryModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            saved_query_from_model,
        )


__all__ = ["SQLAlchemySavedQueryRepository"]
