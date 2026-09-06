"""Contacts facade namespace."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pycrmkit.contacts import (
    Address,
    Contact,
    ContactEmail,
    ContactId,
    ContactPhone,
    ContactQuery,
    ContactService,
    ContactStatus,
    ContactUpdate,
)
from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.facade._runtime import CRMRuntime, present_fields, revision_fields


class ContactsAPI:
    """Transactional facade namespace for Contacts."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def create(
        self,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        display_name: str | None = None,
        status: ContactStatus = ContactStatus.ACTIVE,
        owner_id: EntityId | None = None,
        source: str | None = None,
        emails: Sequence[ContactEmail] = (),
        phones: Sequence[ContactPhone] = (),
        addresses: Sequence[Address] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> Contact:
        with self._runtime.uow_factory() as uow:
            contact = ContactService(
                uow.contacts,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).create(
                first_name=first_name,
                last_name=last_name,
                display_name=display_name,
                status=status,
                owner_id=owner_id,
                source=source,
                emails=emails,
                phones=phones,
                addresses=addresses,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="contact.created",
                aggregate_type="contact",
                aggregate_id=contact.id,
                changes={
                    "fields": present_fields(
                        {
                            "first_name": first_name,
                            "last_name": last_name,
                            "display_name": display_name,
                            "owner_id": owner_id,
                            "source": source,
                            "emails": tuple(emails),
                            "phones": tuple(phones),
                            "addresses": tuple(addresses),
                            "metadata": metadata or {},
                        }
                    )
                },
            )
            uow.commit()
            return contact

    def get(self, contact_id: ContactId) -> Contact:
        with self._runtime.uow_factory() as uow:
            return uow.contacts.get(contact_id)

    def update(self, contact_id: ContactId, changes: ContactUpdate) -> Contact:
        with self._runtime.uow_factory() as uow:
            contact = ContactService(
                uow.contacts,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).update(contact_id, changes)
            self._runtime.record_change(
                uow,
                event_type="contact.updated",
                aggregate_type="contact",
                aggregate_id=contact.id,
                changes={"fields": revision_fields(changes)},
            )
            uow.commit()
            return contact

    def archive(self, contact_id: ContactId) -> Contact:
        with self._runtime.uow_factory() as uow:
            contact = ContactService(
                uow.contacts,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).archive(contact_id)
            self._runtime.record_change(
                uow,
                event_type="contact.archived",
                aggregate_type="contact",
                aggregate_id=contact.id,
                changes={"fields": ["status"]},
            )
            uow.commit()
            return contact

    def search(
        self,
        query: ContactQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Contact]:
        with self._runtime.uow_factory() as uow:
            return ContactService(uow.contacts).search(query, page)
