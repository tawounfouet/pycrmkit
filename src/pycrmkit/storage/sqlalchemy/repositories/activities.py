"""SQLAlchemy ActivityRepository implementation."""

from __future__ import annotations

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from pycrmkit.activities import Activity, ActivityId, ActivityQuery
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.sqlalchemy.mappers import (
    activity_from_model,
    activity_to_model,
)
from pycrmkit.storage.sqlalchemy.models.activity import (
    ActivityModel,
    ActivityParticipantModel,
    ActivityReferenceModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyActivityRepository:
    """SQLAlchemy adapter for generic CRM interactions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, activity_id: ActivityId) -> Activity:
        activity = self.find(activity_id)
        if activity is None:
            raise NotFoundError(
                "activity not found",
                code="activity.not_found",
                context={"activity_id": str(activity_id)},
            )
        return activity

    def find(self, activity_id: ActivityId) -> Activity | None:
        model = self.session.get(ActivityModel, str(activity_id))
        return None if model is None else self._hydrate(model)

    def save(self, activity: Activity) -> None:
        model = self.session.get(ActivityModel, str(activity.id))
        target = activity_to_model(activity, model)
        if model is None:
            self.session.add(target)
        key = str(activity.id)
        self.session.execute(
            delete(ActivityParticipantModel).where(
                ActivityParticipantModel.activity_id == key
            )
        )
        self.session.execute(
            delete(ActivityReferenceModel).where(
                ActivityReferenceModel.activity_id == key
            )
        )
        self.session.add_all(
            [
                ActivityParticipantModel(
                    activity_id=key,
                    position=position,
                    entity_kind=participant.reference.kind,
                    entity_id=str(participant.reference.id),
                    role=participant.role,
                    is_primary=participant.is_primary,
                )
                for position, participant in enumerate(
                    activity.participants
                )
            ]
        )
        self.session.add_all(
            [
                ActivityReferenceModel(
                    activity_id=key,
                    position=position,
                    entity_kind=reference.kind,
                    entity_id=str(reference.id),
                )
                for position, reference in enumerate(
                    activity.references
                )
            ]
        )

    def list(
        self,
        query: ActivityQuery,
        page: OffsetPageRequest,
    ) -> Page[Activity]:
        statement = select(ActivityModel)
        if query.type is not None:
            statement = statement.where(
                ActivityModel.type == query.type.value
            )
        if query.participant is not None:
            statement = statement.where(
                exists(
                    select(ActivityParticipantModel.id).where(
                        ActivityParticipantModel.activity_id
                        == ActivityModel.id,
                        ActivityParticipantModel.entity_kind
                        == query.participant.kind,
                        ActivityParticipantModel.entity_id
                        == str(query.participant.id),
                    )
                )
            )
        if query.reference is not None:
            statement = statement.where(
                exists(
                    select(ActivityReferenceModel.id).where(
                        ActivityReferenceModel.activity_id
                        == ActivityModel.id,
                        ActivityReferenceModel.entity_kind
                        == query.reference.kind,
                        ActivityReferenceModel.entity_id
                        == str(query.reference.id),
                    )
                )
            )
        if query.direction is not None:
            statement = statement.where(
                ActivityModel.direction == query.direction.value
            )
        if query.source is not None:
            statement = statement.where(
                func.lower(ActivityModel.source) == query.source
            )
        if query.external_id is not None:
            statement = statement.where(
                ActivityModel.external_id == query.external_id
            )
        if query.occurred_from is not None:
            statement = statement.where(
                ActivityModel.occurred_at >= query.occurred_from
            )
        if query.occurred_until is not None:
            statement = statement.where(
                ActivityModel.occurred_at < query.occurred_until
            )
        statement = statement.order_by(
            ActivityModel.occurred_at.desc(),
            ActivityModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            self._hydrate,
        )

    def _hydrate(self, model: ActivityModel) -> Activity:
        participants = list(
            self.session.scalars(
                select(ActivityParticipantModel)
                .where(
                    ActivityParticipantModel.activity_id == model.id
                )
                .order_by(
                    ActivityParticipantModel.position.asc(),
                    ActivityParticipantModel.id.asc(),
                )
            )
        )
        references = list(
            self.session.scalars(
                select(ActivityReferenceModel)
                .where(
                    ActivityReferenceModel.activity_id == model.id
                )
                .order_by(
                    ActivityReferenceModel.position.asc(),
                    ActivityReferenceModel.id.asc(),
                )
            )
        )
        return activity_from_model(
            model,
            participants,
            references,
        )
