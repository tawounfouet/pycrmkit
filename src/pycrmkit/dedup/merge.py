"""Pure merge policies, result models and contact-profile consolidation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from pycrmkit.audit import AuditEntry
from pycrmkit.contacts import Contact
from pycrmkit.contacts.policies import resolve_display_name
from pycrmkit.contacts.value_objects import Address, ContactEmail, ContactPhone
from pycrmkit.dedup.provenance import DedupProvenance
from pycrmkit.exceptions import ConflictError, ValidationError


class MergeResolution(StrEnum):
    """Resolution applied when two merge inputs carry competing values."""

    REJECT = "reject"
    KEEP_PRIMARY = "keep_primary"
    KEEP_DUPLICATE = "keep_duplicate"


@dataclass(frozen=True, slots=True)
class MergePolicy:
    """Conservative, configurable V0.9 contact merge policy."""

    primary_email_conflict: MergeResolution = MergeResolution.REJECT
    primary_phone_conflict: MergeResolution = MergeResolution.REJECT
    custom_field_conflict: MergeResolution = MergeResolution.REJECT
    require_duplicate_provenance: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "primary_email_conflict",
            MergeResolution(self.primary_email_conflict),
        )
        object.__setattr__(
            self,
            "primary_phone_conflict",
            MergeResolution(self.primary_phone_conflict),
        )
        object.__setattr__(
            self,
            "custom_field_conflict",
            MergeResolution(self.custom_field_conflict),
        )


@dataclass(frozen=True, slots=True)
class MergeStatistics:
    """Observable mutation counts produced by one committed merge."""

    activities_reassigned: int = 0
    relationships_reassigned: int = 0
    relationships_ended: int = 0
    tags_added: int = 0
    custom_fields_moved: int = 0
    custom_field_conflicts: int = 0
    external_identities_moved: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "activities_reassigned": self.activities_reassigned,
            "relationships_reassigned": self.relationships_reassigned,
            "relationships_ended": self.relationships_ended,
            "tags_added": self.tags_added,
            "custom_fields_moved": self.custom_fields_moved,
            "custom_field_conflicts": self.custom_field_conflicts,
            "external_identities_moved": self.external_identities_moved,
        }


@dataclass(frozen=True, slots=True)
class MergeResult:
    """Committed merge outcome including audit and dedup provenance."""

    primary: Contact
    duplicate: Contact
    statistics: MergeStatistics
    audit_entry: AuditEntry
    provenance: DedupProvenance | None = None


def _resolve_primary_key(
    *,
    primary_key: str | None,
    duplicate_key: str | None,
    resolution: MergeResolution,
    conflict_code: str,
    conflict_message: str,
) -> str | None:
    if primary_key is None:
        return duplicate_key
    if duplicate_key is None or duplicate_key == primary_key:
        return primary_key
    if resolution is MergeResolution.REJECT:
        raise ConflictError(
            conflict_message,
            code=conflict_code,
            context={
                "primary": primary_key,
                "duplicate": duplicate_key,
            },
        )
    if resolution is MergeResolution.KEEP_DUPLICATE:
        return duplicate_key
    return primary_key


def _merge_emails(
    primary: tuple[ContactEmail, ...],
    duplicate: tuple[ContactEmail, ...],
    resolution: MergeResolution,
) -> tuple[ContactEmail, ...]:
    primary_key = next(
        (email.normalized for email in primary if email.is_primary),
        None,
    )
    duplicate_key = next(
        (email.normalized for email in duplicate if email.is_primary),
        None,
    )
    selected = _resolve_primary_key(
        primary_key=primary_key,
        duplicate_key=duplicate_key,
        resolution=resolution,
        conflict_code="merge.contact.email_primary.conflict",
        conflict_message="primary and duplicate contacts have different primary emails",
    )

    ordered: list[ContactEmail] = []
    seen: set[str] = set()
    for email in (*primary, *duplicate):
        if email.normalized in seen:
            continue
        seen.add(email.normalized)
        ordered.append(email)

    return tuple(
        replace(email, is_primary=email.normalized == selected)
        for email in ordered
    )


def _merge_phones(
    primary: tuple[ContactPhone, ...],
    duplicate: tuple[ContactPhone, ...],
    resolution: MergeResolution,
) -> tuple[ContactPhone, ...]:
    primary_key = next(
        (phone.normalized for phone in primary if phone.is_primary),
        None,
    )
    duplicate_key = next(
        (phone.normalized for phone in duplicate if phone.is_primary),
        None,
    )
    selected = _resolve_primary_key(
        primary_key=primary_key,
        duplicate_key=duplicate_key,
        resolution=resolution,
        conflict_code="merge.contact.phone_primary.conflict",
        conflict_message="primary and duplicate contacts have different primary phones",
    )

    ordered: list[ContactPhone] = []
    seen: set[str] = set()
    for phone in (*primary, *duplicate):
        if phone.normalized in seen:
            continue
        seen.add(phone.normalized)
        ordered.append(phone)

    return tuple(
        replace(phone, is_primary=phone.normalized == selected)
        for phone in ordered
    )


def _address_key(address: Address) -> tuple[str | None, ...]:
    return (
        address.line1.casefold(),
        address.line2.casefold() if address.line2 else None,
        address.postal_code.casefold() if address.postal_code else None,
        address.city.casefold(),
        address.region.casefold() if address.region else None,
        address.country_code.casefold() if address.country_code else None,
    )


def _merge_addresses(
    primary: tuple[Address, ...],
    duplicate: tuple[Address, ...],
) -> tuple[Address, ...]:
    selected = next(
        (_address_key(address) for address in primary if address.is_primary),
        None,
    )
    if selected is None:
        selected = next(
            (_address_key(address) for address in duplicate if address.is_primary),
            None,
        )

    ordered: list[Address] = []
    seen: set[tuple[str | None, ...]] = set()
    for address in (*primary, *duplicate):
        key = _address_key(address)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(address)

    return tuple(
        replace(address, is_primary=_address_key(address) == selected)
        for address in ordered
    )


def merge_contact_profile(
    primary: Contact,
    duplicate: Contact,
    *,
    at: datetime,
    policy: MergePolicy,
) -> Contact:
    """Return the consolidated primary Contact without persisting it."""

    if primary.id == duplicate.id:
        raise ValidationError(
            "primary and duplicate contacts must be different records",
            code="merge.contact.same_record",
        )
    primary.ensure_mutable()
    duplicate.ensure_mutable()

    metadata = dict(duplicate.metadata)
    metadata.update(primary.metadata)

    first_name = primary.first_name or duplicate.first_name
    last_name = primary.last_name or duplicate.last_name
    current_derived_name = resolve_display_name(
        first_name=primary.first_name,
        last_name=primary.last_name,
        explicit=None,
    )
    if primary.display_name == current_derived_name:
        display_name = resolve_display_name(
            first_name=first_name,
            last_name=last_name,
            explicit=None,
        )
    else:
        display_name = primary.display_name or duplicate.display_name

    return replace(
        primary,
        updated_at=at,
        first_name=first_name,
        last_name=last_name,
        display_name=display_name,
        owner_id=primary.owner_id or duplicate.owner_id,
        source=primary.source or duplicate.source,
        emails=_merge_emails(
            primary.emails,
            duplicate.emails,
            policy.primary_email_conflict,
        ),
        phones=_merge_phones(
            primary.phones,
            duplicate.phones,
            policy.primary_phone_conflict,
        ),
        addresses=_merge_addresses(primary.addresses, duplicate.addresses),
        metadata=metadata,
    )


__all__ = [
    "MergePolicy",
    "MergeResolution",
    "MergeResult",
    "MergeStatistics",
    "merge_contact_profile",
]
