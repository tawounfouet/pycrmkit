"""Pure contact-profile merge behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import Contact, ContactEmail, ContactId, ContactPhone
from pycrmkit.dedup import MergePolicy, MergeResolution, merge_contact_profile
from pycrmkit.exceptions import ConflictError


CREATED_AT = datetime(2026, 9, 27, 8, tzinfo=UTC)
MERGED_AT = datetime(2026, 9, 27, 9, tzinfo=UTC)


def _contact(
    suffix: int,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    emails: tuple[ContactEmail, ...] = (),
    phones: tuple[ContactPhone, ...] = (),
    metadata: dict[str, object] | None = None,
) -> Contact:
    return Contact(
        id=ContactId(UUID(f"00000000-0000-4000-8000-{suffix:012d}")),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        first_name=first_name,
        last_name=last_name,
        emails=emails,
        phones=phones,
        metadata=metadata or {},
    )


def test_merge_rejects_conflicting_primary_emails_by_default() -> None:
    primary = _contact(
        101,
        first_name="Ada",
        emails=(ContactEmail("ada@example.com", is_primary=True),),
    )
    duplicate = _contact(
        102,
        first_name="Ada",
        emails=(ContactEmail("ada.alt@example.com", is_primary=True),),
    )

    with pytest.raises(ConflictError) as error:
        merge_contact_profile(
            primary,
            duplicate,
            at=MERGED_AT,
            policy=MergePolicy(),
        )

    assert error.value.code == "merge.contact.email_primary.conflict"


def test_merge_email_conflict_policy_can_keep_primary_or_duplicate() -> None:
    primary = _contact(
        101,
        first_name="Ada",
        emails=(ContactEmail("ada@example.com", is_primary=True),),
    )
    duplicate = _contact(
        102,
        first_name="Ada",
        emails=(ContactEmail("ada.alt@example.com", is_primary=True),),
    )

    keep_primary = merge_contact_profile(
        primary,
        duplicate,
        at=MERGED_AT,
        policy=MergePolicy(
            primary_email_conflict=MergeResolution.KEEP_PRIMARY,
        ),
    )
    keep_duplicate = merge_contact_profile(
        primary,
        duplicate,
        at=MERGED_AT,
        policy=MergePolicy(
            primary_email_conflict=MergeResolution.KEEP_DUPLICATE,
        ),
    )

    assert {email.value for email in keep_primary.emails} == {
        "ada@example.com",
        "ada.alt@example.com",
    }
    assert [email.value for email in keep_primary.emails if email.is_primary] == [
        "ada@example.com"
    ]
    assert [email.value for email in keep_duplicate.emails if email.is_primary] == [
        "ada.alt@example.com"
    ]


def test_merge_rejects_conflicting_primary_phones_by_default() -> None:
    primary = _contact(
        101,
        first_name="Ada",
        phones=(ContactPhone("+33111111111", is_primary=True),),
    )
    duplicate = _contact(
        102,
        first_name="Ada",
        phones=(ContactPhone("+33222222222", is_primary=True),),
    )

    with pytest.raises(ConflictError) as error:
        merge_contact_profile(
            primary,
            duplicate,
            at=MERGED_AT,
            policy=MergePolicy(),
        )

    assert error.value.code == "merge.contact.phone_primary.conflict"


def test_merge_coalesces_missing_profile_fields_and_preserves_primary_metadata() -> None:
    primary = _contact(
        101,
        last_name="Lovelace",
        emails=(ContactEmail("ada@example.com", is_primary=True),),
        metadata={"owner_note": "primary", "shared": "primary"},
    )
    duplicate = _contact(
        102,
        first_name="Ada",
        emails=(ContactEmail("ADA@example.com", is_primary=True),),
        phones=(ContactPhone("+33612345678", is_primary=True),),
        metadata={"source_note": "duplicate", "shared": "duplicate"},
    )

    merged = merge_contact_profile(
        primary,
        duplicate,
        at=MERGED_AT,
        policy=MergePolicy(),
    )

    assert merged.first_name == "Ada"
    assert merged.last_name == "Lovelace"
    assert len(merged.emails) == 1
    assert merged.emails[0].normalized == "ada@example.com"
    assert merged.phones[0].normalized == "+33612345678"
    assert merged.metadata == {
        "source_note": "duplicate",
        "shared": "primary",
        "owner_note": "primary",
    }
    assert merged.updated_at == MERGED_AT
