"""SQLAlchemy ContactRepository implementation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, exists, func, literal, select
from sqlalchemy.orm import Session

from pycrmkit.contacts import Contact, ContactId, ContactQuery, ContactStatus
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.sqlalchemy.mappers import contact_from_model, contact_to_model
from pycrmkit.storage.sqlalchemy.models.contact import (
    ContactAddressModel,
    ContactEmailModel,
    ContactModel,
    ContactPhoneModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyContactRepository:
    """Session-scoped SQLAlchemy adapter for the Contact repository contract."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, contact_id: ContactId) -> Contact:
        contact = self.find(contact_id)
        if contact is None:
            raise NotFoundError(
                "Contact not found",
                code="contact.not_found",
                context={"contact_id": str(contact_id)},
            )
        return contact

    def find(self, contact_id: ContactId) -> Contact | None:
        model = self.session.get(ContactModel, str(contact_id))
        if model is None:
            return None
        return self._hydrate(model)

    def save(self, contact: Contact) -> None:
        model = self.session.get(ContactModel, str(contact.id))
        target = contact_to_model(contact, model)
        if model is None:
            self.session.add(target)

        key = str(contact.id)
        self.session.execute(
            delete(ContactEmailModel).where(ContactEmailModel.contact_id == key)
        )
        self.session.execute(
            delete(ContactPhoneModel).where(ContactPhoneModel.contact_id == key)
        )
        self.session.execute(
            delete(ContactAddressModel).where(ContactAddressModel.contact_id == key)
        )
        self.session.add_all(
            [
                ContactEmailModel(
                    contact_id=key,
                    position=position,
                    value=value.value,
                    normalized=value.normalized,
                    is_primary=value.is_primary,
                    verification=value.verification.value,
                )
                for position, value in enumerate(contact.emails)
            ]
        )
        self.session.add_all(
            [
                ContactPhoneModel(
                    contact_id=key,
                    position=position,
                    value=value.value,
                    normalized=value.normalized,
                    is_primary=value.is_primary,
                    verification=value.verification.value,
                )
                for position, value in enumerate(contact.phones)
            ]
        )
        self.session.add_all(
            [
                ContactAddressModel(
                    contact_id=key,
                    position=position,
                    line1=value.line1,
                    line2=value.line2,
                    city=value.city,
                    postal_code=value.postal_code,
                    region=value.region,
                    country_code=value.country_code,
                    is_primary=value.is_primary,
                )
                for position, value in enumerate(contact.addresses)
            ]
        )

    def archive(
        self,
        contact_id: ContactId,
        archived_at: datetime,
    ) -> Contact:
        contact = self.get(contact_id)
        contact.archive(archived_at)
        self.save(contact)
        return contact

    def search(
        self,
        query: ContactQuery,
        page: OffsetPageRequest,
    ) -> Page[Contact]:
        statement = select(ContactModel)
        if not query.include_archived:
            statement = statement.where(
                ContactModel.status != ContactStatus.ARCHIVED.value
            )
        if query.status is not None:
            statement = statement.where(ContactModel.status == query.status.value)
        if query.email is not None:
            statement = statement.where(
                exists(
                    select(ContactEmailModel.id).where(
                        ContactEmailModel.contact_id == ContactModel.id,
                        ContactEmailModel.normalized == query.email,
                    )
                )
            )
        if query.phone is not None:
            statement = statement.where(
                exists(
                    select(ContactPhoneModel.id).where(
                        ContactPhoneModel.contact_id == ContactModel.id,
                        ContactPhoneModel.normalized == query.phone,
                    )
                )
            )
        if query.name is not None:
            haystack = func.lower(
                func.coalesce(ContactModel.first_name, "")
                + literal(" ")
                + func.coalesce(ContactModel.last_name, "")
                + literal(" ")
                + func.coalesce(ContactModel.display_name, "")
            )
            statement = statement.where(
                haystack.contains(query.name.casefold())
            )
        if query.owner_id is not None:
            statement = statement.where(
                ContactModel.owner_id == str(query.owner_id)
            )
        if query.source is not None:
            statement = statement.where(
                func.lower(ContactModel.source) == query.source.casefold()
            )
        statement = statement.order_by(
            ContactModel.created_at.asc(),
            ContactModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            self._hydrate,
        )

    def _hydrate(self, model: ContactModel) -> Contact:
        key = model.id
        emails = list(
            self.session.scalars(
                select(ContactEmailModel)
                .where(ContactEmailModel.contact_id == key)
                .order_by(
                    ContactEmailModel.position.asc(),
                    ContactEmailModel.id.asc(),
                )
            )
        )
        phones = list(
            self.session.scalars(
                select(ContactPhoneModel)
                .where(ContactPhoneModel.contact_id == key)
                .order_by(
                    ContactPhoneModel.position.asc(),
                    ContactPhoneModel.id.asc(),
                )
            )
        )
        addresses = list(
            self.session.scalars(
                select(ContactAddressModel)
                .where(ContactAddressModel.contact_id == key)
                .order_by(
                    ContactAddressModel.position.asc(),
                    ContactAddressModel.id.asc(),
                )
            )
        )
        return contact_from_model(model, emails, phones, addresses)
