"""SQLAlchemy repositories for Segment definitions and stored membership."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.segments import (
    Segment,
    SegmentId,
    SegmentMember,
    SegmentQuery,
    SegmentStatus,
    normalize_segment_key,
)
from pycrmkit.storage.sqlalchemy.models.segmentation import (
    SegmentMemberModel,
    SegmentModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models
from pycrmkit.storage.sqlalchemy.segmentation_codec import (
    segment_from_model,
    segment_member_from_model,
    segment_member_to_model,
    segment_to_model,
)


class SQLAlchemySegmentRepository:
    """Current-state Segment repository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, segment_id: SegmentId) -> Segment:
        segment = self.find(segment_id)
        if segment is None:
            raise NotFoundError(
                "Segment not found",
                code="segment.not_found",
                context={"segment_id": str(segment_id)},
            )
        return segment

    def find(self, segment_id: SegmentId) -> Segment | None:
        model = self.session.get(SegmentModel, str(segment_id))
        return None if model is None else segment_from_model(model)

    def find_by_key(self, key: str) -> Segment | None:
        normalized = normalize_segment_key(key)
        model = self.session.scalar(
            select(SegmentModel).where(SegmentModel.key == normalized)
        )
        return None if model is None else segment_from_model(model)

    def save(self, segment: Segment) -> None:
        with self.session.no_autoflush:
            by_key = self.session.scalar(
                select(SegmentModel).where(SegmentModel.key == segment.key)
            )
            current = self.session.get(SegmentModel, str(segment.id))

        if by_key is not None and by_key.id != str(segment.id):
            raise DuplicateError(
                "Segment key already exists",
                code="segment.key.duplicate",
                context={"key": segment.key},
            )
        if current is not None and segment.revision < current.revision:
            raise ConflictError(
                "Segment revision has changed",
                code="segment.revision.conflict",
                context={
                    "expected_at_least": current.revision,
                    "actual": segment.revision,
                },
            )

        target = segment_to_model(segment, current)
        if current is None:
            self.session.add(target)

    def search(
        self,
        query: SegmentQuery,
        page: OffsetPageRequest,
    ) -> Page[Segment]:
        statement = select(SegmentModel)
        if not query.include_archived:
            statement = statement.where(
                SegmentModel.status != SegmentStatus.ARCHIVED.value
            )
        if query.status is not None:
            statement = statement.where(SegmentModel.status == query.status.value)
        if query.mode is not None:
            statement = statement.where(SegmentModel.mode == query.mode.value)
        if query.entity_kind is not None:
            statement = statement.where(
                SegmentModel.entity_kind == query.entity_kind
            )
        if query.owner_id is not None:
            statement = statement.where(
                SegmentModel.owner_id == str(query.owner_id)
            )
        statement = statement.order_by(
            SegmentModel.created_at.asc(),
            SegmentModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            segment_from_model,
        )


class SQLAlchemySegmentMembershipRepository:
    """Stored Static/Snapshot membership repository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, member: SegmentMember) -> SegmentMember:
        existing = self.session.scalar(
            select(SegmentMemberModel.id).where(
                SegmentMemberModel.segment_id == str(member.segment_id),
                SegmentMemberModel.entity_kind == member.entity.kind,
                SegmentMemberModel.entity_id == str(member.entity.id),
            )
        )
        if existing is not None:
            raise DuplicateError(
                "Segment membership already exists",
                code="segment.member.duplicate",
                context={
                    "segment_id": str(member.segment_id),
                    "entity_kind": member.entity.kind,
                    "entity_id": str(member.entity.id),
                },
            )
        self.session.add(segment_member_to_model(member))
        return member

    def remove(
        self,
        segment_id: SegmentId,
        entity: EntityReference,
    ) -> bool:
        existing = self.session.scalar(
            select(SegmentMemberModel.id).where(
                SegmentMemberModel.segment_id == str(segment_id),
                SegmentMemberModel.entity_kind == entity.kind,
                SegmentMemberModel.entity_id == str(entity.id),
            )
        )
        if existing is None:
            return False
        self.session.execute(
            delete(SegmentMemberModel).where(
                SegmentMemberModel.segment_id == str(segment_id),
                SegmentMemberModel.entity_kind == entity.kind,
                SegmentMemberModel.entity_id == str(entity.id),
            )
        )
        return True

    def contains(
        self,
        segment_id: SegmentId,
        entity: EntityReference,
    ) -> bool:
        return (
            self.session.scalar(
                select(SegmentMemberModel.id).where(
                    SegmentMemberModel.segment_id == str(segment_id),
                    SegmentMemberModel.entity_kind == entity.kind,
                    SegmentMemberModel.entity_id == str(entity.id),
                )
            )
            is not None
        )

    def list(
        self,
        segment_id: SegmentId,
        page: OffsetPageRequest,
    ) -> Page[SegmentMember]:
        statement = (
            select(SegmentMemberModel)
            .where(SegmentMemberModel.segment_id == str(segment_id))
            .order_by(
                SegmentMemberModel.added_at.asc(),
                SegmentMemberModel.entity_kind.asc(),
                SegmentMemberModel.entity_id.asc(),
            )
        )
        total = int(
            self.session.scalar(
                select(func.count()).select_from(
                    statement.order_by(None).subquery()
                )
            )
            or 0
        )
        models = self.session.scalars(
            statement.offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=tuple(
                segment_member_from_model(model)
                for model in models
            ),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def count(self, segment_id: SegmentId) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(SegmentMemberModel)
                .where(SegmentMemberModel.segment_id == str(segment_id))
            )
            or 0
        )


__all__ = [
    "SQLAlchemySegmentMembershipRepository",
    "SQLAlchemySegmentRepository",
]
