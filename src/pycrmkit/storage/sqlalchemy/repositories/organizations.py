"""SQLAlchemy OrganizationRepository implementation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, exists, func, literal, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.organizations import (
    Organization,
    OrganizationId,
    OrganizationQuery,
    OrganizationStatus,
)
from pycrmkit.storage.sqlalchemy.mappers import (
    organization_from_model,
    organization_to_model,
)
from pycrmkit.storage.sqlalchemy.models.organization import (
    OrganizationAddressModel,
    OrganizationDomainModel,
    OrganizationModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyOrganizationRepository:
    """Session-scoped SQLAlchemy adapter for Organization persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, organization_id: OrganizationId) -> Organization:
        organization = self.find(organization_id)
        if organization is None:
            raise NotFoundError(
                "Organization not found",
                code="organization.not_found",
                context={"organization_id": str(organization_id)},
            )
        return organization

    def find(
        self,
        organization_id: OrganizationId,
    ) -> Organization | None:
        model = self.session.get(
            OrganizationModel,
            str(organization_id),
        )
        return None if model is None else self._hydrate(model)

    def save(self, organization: Organization) -> None:
        model = self.session.get(
            OrganizationModel,
            str(organization.id),
        )
        target = organization_to_model(organization, model)
        if model is None:
            self.session.add(target)

        key = str(organization.id)
        self.session.execute(
            delete(OrganizationDomainModel).where(
                OrganizationDomainModel.organization_id == key
            )
        )
        self.session.execute(
            delete(OrganizationAddressModel).where(
                OrganizationAddressModel.organization_id == key
            )
        )
        self.session.add_all(
            [
                OrganizationDomainModel(
                    organization_id=key,
                    position=position,
                    value=value.value,
                    normalized=value.normalized,
                    is_primary=value.is_primary,
                )
                for position, value in enumerate(organization.domains)
            ]
        )
        self.session.add_all(
            [
                OrganizationAddressModel(
                    organization_id=key,
                    position=position,
                    line1=value.line1,
                    line2=value.line2,
                    city=value.city,
                    postal_code=value.postal_code,
                    region=value.region,
                    country_code=value.country_code,
                    is_primary=value.is_primary,
                )
                for position, value in enumerate(organization.addresses)
            ]
        )

    def archive(
        self,
        organization_id: OrganizationId,
        archived_at: datetime,
    ) -> Organization:
        organization = self.get(organization_id)
        organization.archive(archived_at)
        self.save(organization)
        return organization

    def search(
        self,
        query: OrganizationQuery,
        page: OffsetPageRequest,
    ) -> Page[Organization]:
        statement = select(OrganizationModel)
        if not query.include_archived:
            statement = statement.where(
                OrganizationModel.status
                != OrganizationStatus.ARCHIVED.value
            )
        if query.status is not None:
            statement = statement.where(
                OrganizationModel.status == query.status.value
            )
        if query.domain is not None:
            statement = statement.where(
                exists(
                    select(OrganizationDomainModel.id).where(
                        OrganizationDomainModel.organization_id
                        == OrganizationModel.id,
                        OrganizationDomainModel.normalized == query.domain,
                    )
                )
            )
        if query.name is not None:
            haystack = func.lower(
                func.coalesce(OrganizationModel.legal_name, "")
                + literal(" ")
                + func.coalesce(OrganizationModel.trading_name, "")
                + literal(" ")
                + func.coalesce(OrganizationModel.display_name, "")
            )
            statement = statement.where(
                haystack.contains(query.name.casefold())
            )
        if query.registration_number is not None:
            statement = statement.where(
                func.lower(OrganizationModel.registration_number)
                == query.registration_number.casefold()
            )
        if query.owner_id is not None:
            statement = statement.where(
                OrganizationModel.owner_id == str(query.owner_id)
            )
        if query.source is not None:
            statement = statement.where(
                func.lower(OrganizationModel.source)
                == query.source.casefold()
            )
        statement = statement.order_by(
            OrganizationModel.created_at.asc(),
            OrganizationModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            self._hydrate,
        )

    def _hydrate(
        self,
        model: OrganizationModel,
    ) -> Organization:
        domains = list(
            self.session.scalars(
                select(OrganizationDomainModel)
                .where(
                    OrganizationDomainModel.organization_id
                    == model.id
                )
                .order_by(
                    OrganizationDomainModel.position.asc(),
                    OrganizationDomainModel.id.asc(),
                )
            )
        )
        addresses = list(
            self.session.scalars(
                select(OrganizationAddressModel)
                .where(
                    OrganizationAddressModel.organization_id
                    == model.id
                )
                .order_by(
                    OrganizationAddressModel.position.asc(),
                    OrganizationAddressModel.id.asc(),
                )
            )
        )
        return organization_from_model(
            model,
            domains,
            addresses,
        )
