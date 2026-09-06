from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.contacts import Contact, ContactEmail, ContactId, ContactStatus
from pycrmkit.exceptions import ConflictError, InvalidStateError, ValidationError

NOW = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
CONTACT_ID = ContactId(UUID("00000000-0000-4000-8000-000000000001"))


def test_contact_derives_display_name_and_normalizes_profile() -> None:
    contact = Contact(
        id=CONTACT_ID,
        created_at=NOW,
        updated_at=NOW,
        first_name=" Thomas ",
        last_name="  Awounfouet ",
        source="  Referral ",
    )
    assert contact.first_name == "Thomas"
    assert contact.last_name == "Awounfouet"
    assert contact.display_name == "Thomas Awounfouet"
    assert contact.source == "Referral"


def test_contact_requires_identity_signal() -> None:
    with pytest.raises(ValidationError, match="name, email, or phone"):
        Contact(id=CONTACT_ID, created_at=NOW, updated_at=NOW)


def test_contact_rejects_duplicate_email_and_multiple_primary() -> None:
    with pytest.raises(ConflictError, match="duplicate email"):
        Contact(
            id=CONTACT_ID,
            created_at=NOW,
            updated_at=NOW,
            emails=(ContactEmail("a@example.com"), ContactEmail("A@EXAMPLE.COM")),
        )
    with pytest.raises(ValidationError, match="primary email"):
        Contact(
            id=CONTACT_ID,
            created_at=NOW,
            updated_at=NOW,
            emails=(
                ContactEmail("a@example.com", is_primary=True),
                ContactEmail("b@example.com", is_primary=True),
            ),
        )


def test_contact_archive_is_idempotent_and_blocks_updates() -> None:
    contact = Contact(id=CONTACT_ID, created_at=NOW, updated_at=NOW, first_name="Thomas")
    archived_at = NOW + timedelta(hours=1)
    contact.archive(archived_at)
    contact.archive(archived_at + timedelta(hours=1))
    assert contact.status is ContactStatus.ARCHIVED
    assert contact.archived_at == archived_at
    assert contact.updated_at == archived_at
    with pytest.raises(InvalidStateError, match="archived"):
        contact.ensure_mutable()
