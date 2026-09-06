"""Contact-domain normalization and invariant policies."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from pycrmkit.contacts.value_objects import Address, ContactEmail, ContactPhone
from pycrmkit.exceptions import ConflictError, ValidationError

_WHITESPACE = re.compile(r"\s+")


def normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional human text without changing meaningful letter case."""
    if value is None:
        return None
    normalized = _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())
    return normalized or None


def resolve_display_name(*, first_name: str | None, last_name: str | None, explicit: str | None) -> str | None:
    """Return an explicit display name or derive one from first/last names."""
    normalized_explicit = normalize_optional_text(explicit)
    if normalized_explicit:
        return normalized_explicit
    parts = [normalize_optional_text(first_name), normalize_optional_text(last_name)]
    combined = " ".join(part for part in parts if part)
    return combined or None


def validate_contact_points(*, emails: Iterable[ContactEmail], phones: Iterable[ContactPhone], addresses: Iterable[Address]) -> None:
    """Reject duplicate normalized points and multiple primaries per point type."""
    email_values: set[str] = set()
    phone_values: set[str] = set()
    primary_emails = primary_phones = primary_addresses = 0
    for email in emails:
        if email.normalized in email_values:
            raise ConflictError("duplicate email within contact", code="contact.email.duplicate", context={"email": email.normalized})
        email_values.add(email.normalized)
        primary_emails += int(email.is_primary)
    for phone in phones:
        if phone.normalized in phone_values:
            raise ConflictError("duplicate phone within contact", code="contact.phone.duplicate", context={"phone": phone.normalized})
        phone_values.add(phone.normalized)
        primary_phones += int(phone.is_primary)
    for address in addresses:
        primary_addresses += int(address.is_primary)
    if primary_emails > 1:
        raise ValidationError("a contact cannot have more than one primary email", code="contact.email.multiple_primary")
    if primary_phones > 1:
        raise ValidationError("a contact cannot have more than one primary phone", code="contact.phone.multiple_primary")
    if primary_addresses > 1:
        raise ValidationError("a contact cannot have more than one primary address", code="contact.address.multiple_primary")


def validate_contact_identity(*, first_name: str | None, last_name: str | None, display_name: str | None, emails: Iterable[ContactEmail], phones: Iterable[ContactPhone]) -> None:
    """Require at least one usable CRM identity signal."""
    if any((first_name, last_name, display_name)):
        return
    if any(True for _ in emails) or any(True for _ in phones):
        return
    raise ValidationError("contact requires a name, email, or phone", code="contact.identity.required")
