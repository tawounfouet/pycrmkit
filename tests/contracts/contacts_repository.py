"""Reusable ContactRepository behavioral contract suite."""

from __future__ import annotations

from datetime import timedelta

import pytest

from pycrmkit.contacts import Contact, ContactQuery, ContactRepository, ContactStatus
from pycrmkit.core import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError


class ContactRepositoryContract:
    """Assertions every ContactRepository adapter must satisfy."""

    def test_save_and_get(self, repository: ContactRepository, contact: Contact) -> None:
        repository.save(contact)
        loaded = repository.get(contact.id)
        assert loaded == contact
        assert loaded.display_name == contact.display_name

    def test_missing_get_raises_and_find_returns_none(
        self,
        repository: ContactRepository,
        missing_contact_id,
    ) -> None:
        with pytest.raises(NotFoundError):
            repository.get(missing_contact_id)
        assert repository.find(missing_contact_id) is None

    def test_save_replaces_current_domain_state(
        self,
        repository: ContactRepository,
        contact: Contact,
    ) -> None:
        repository.save(contact)
        contact.source = "updated-source"
        repository.save(contact)
        assert repository.get(contact.id).source == "updated-source"

    def test_search_is_deterministic_and_exactly_paginated(
        self,
        repository: ContactRepository,
        contact: Contact,
        second_contact: Contact,
    ) -> None:
        repository.save(second_contact)
        repository.save(contact)
        first = repository.search(ContactQuery(), OffsetPageRequest(limit=1, offset=0))
        second = repository.search(ContactQuery(), OffsetPageRequest(limit=1, offset=1))
        expected = sorted((contact, second_contact), key=lambda item: (item.created_at, item.id))
        assert first.items == (expected[0],)
        assert second.items == (expected[1],)
        assert first.total == 2
        assert first.has_next is True
        assert second.has_previous is True

    def test_search_filters_normalized_email(
        self,
        repository: ContactRepository,
        contact: Contact,
    ) -> None:
        repository.save(contact)
        page = repository.search(
            ContactQuery(email="CONTACT@EXAMPLE.COM"),
            OffsetPageRequest(),
        )
        assert page.items == (contact,)

    def test_archive_is_hidden_by_default_and_can_be_included(
        self,
        repository: ContactRepository,
        contact: Contact,
    ) -> None:
        repository.save(contact)
        archived = repository.archive(contact.id, contact.created_at + timedelta(hours=1))
        default_page = repository.search(ContactQuery(), OffsetPageRequest())
        inclusive_page = repository.search(
            ContactQuery(include_archived=True),
            OffsetPageRequest(),
        )
        assert archived.status is ContactStatus.ARCHIVED
        assert default_page.items == ()
        assert inclusive_page.items == (archived,)
