"""SQLAlchemy ExternalIdentityRepository implementation."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ConflictError, DuplicateError
from pycrmkit.external_identities import (
    ExternalIdentity,
    ExternalIdentityId,
    normalize_external_id,
    normalize_external_system,
    same_entity,
)
from pycrmkit.storage.sqlalchemy.mappers import aware
from pycrmkit.storage.sqlalchemy.models.external_identity import ExternalIdentityModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


def _from_model(model: ExternalIdentityModel) -> ExternalIdentity:
    return ExternalIdentity(
        id=ExternalIdentityId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        system=model.system,
        external_id=model.external_id,
        entity_type=model.entity_type,
        entity_id=EntityId.parse(model.entity_id),
        metadata=dict(model.metadata_json or {}),
    )


class SQLAlchemyExternalIdentityRepository:
    """Session-scoped adapter enforcing unique external record ownership."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find(self, system: str, external_id: str) -> ExternalIdentity | None:
        normalized_system = normalize_external_system(system)
        normalized_external_id = normalize_external_id(external_id)
        model = self.session.scalar(
            select(ExternalIdentityModel).where(
                ExternalIdentityModel.system == normalized_system,
                ExternalIdentityModel.external_id == normalized_external_id,
            )
        )
        return None if model is None else _from_model(model)

    def save(self, identity: ExternalIdentity) -> None:
        with self.session.no_autoflush:
            existing = self.find(identity.system, identity.external_id)
        if existing is not None and existing.id != identity.id:
            if not same_entity(existing, identity.entity):
                raise ConflictError(
                    "External identity is already attached to another entity",
                    code="external_identity.owner.conflict",
                    context={
                        "system": identity.system,
                        "external_id": identity.external_id,
                        "owner_type": existing.entity_type,
                        "owner_id": str(existing.entity_id),
                    },
                )
            raise DuplicateError(
                "External identity mapping already exists",
                code="external_identity.duplicate",
                context={
                    "system": identity.system,
                    "external_id": identity.external_id,
                },
            )

        model = self.session.get(ExternalIdentityModel, str(identity.id))
        if model is None:
            model = ExternalIdentityModel(
                id=str(identity.id),
                created_at=identity.created_at,
                updated_at=identity.updated_at,
                system=identity.system,
                external_id=identity.external_id,
                entity_type=identity.entity_type,
                entity_id=str(identity.entity_id),
                metadata_json=dict(identity.metadata),
            )
            self.session.add(model)
            return

        model.updated_at = identity.updated_at
        model.system = identity.system
        model.external_id = identity.external_id
        model.entity_type = identity.entity_type
        model.entity_id = str(identity.entity_id)
        model.metadata_json = dict(identity.metadata)

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[ExternalIdentity]:
        statement = (
            select(ExternalIdentityModel)
            .where(
                ExternalIdentityModel.entity_type == entity.kind,
                ExternalIdentityModel.entity_id == str(entity.id),
            )
            .order_by(
                ExternalIdentityModel.system.asc(),
                ExternalIdentityModel.external_id.asc(),
                ExternalIdentityModel.id.asc(),
            )
        )
        return page_models(self.session, statement, page, _from_model)

    def remove(self, system: str, external_id: str) -> bool:
        normalized_system = normalize_external_system(system)
        normalized_external_id = normalize_external_id(external_id)
        existing = self.session.scalar(
            select(ExternalIdentityModel.id).where(
                ExternalIdentityModel.system == normalized_system,
                ExternalIdentityModel.external_id == normalized_external_id,
            )
        )
        if existing is None:
            return False
        self.session.execute(
            delete(ExternalIdentityModel).where(
                ExternalIdentityModel.system == normalized_system,
                ExternalIdentityModel.external_id == normalized_external_id,
            )
        )
        return True


__all__ = ["SQLAlchemyExternalIdentityRepository"]
