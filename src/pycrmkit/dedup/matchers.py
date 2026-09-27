"""Signal extraction and matcher behavior for duplicate detection."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from pycrmkit.contacts.value_objects import normalize_email, normalize_phone
from pycrmkit.external_identities.entities import (
    normalize_external_id,
    normalize_external_system,
)
from pycrmkit.exceptions import ValidationError

_WHITESPACE = re.compile(r"\s+")


class DedupSignal(StrEnum):
    """Supported evidence channels for V0.9 deduplication."""

    EMAIL = "email"
    PHONE = "phone"
    FULL_NAME = "full_name"
    ORGANIZATION = "organization"
    ADDRESS = "address"
    EXTERNAL_IDENTITY = "external_identity"
    CUSTOM_IDENTIFIER = "custom_identifier"


@dataclass(frozen=True, slots=True)
class SignalMatch:
    """One exact normalized signal match between two records."""

    signal: DedupSignal
    value: str
    key: str | None = None


def normalize_text(value: str) -> str:
    """Normalize human text for conservative case-insensitive equality."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    return _WHITESPACE.sub(" ", normalized).casefold()


def _as_items(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(value)
    return (value,)


def _string_values(value: object) -> tuple[str, ...]:
    output: list[str] = []
    for item in _as_items(value):
        if isinstance(item, str) and item.strip():
            output.append(item)
        elif isinstance(item, Mapping):
            raw = item.get("normalized", item.get("value"))
            if isinstance(raw, str) and raw.strip():
                output.append(raw)
    return tuple(output)


def _first_non_empty(mapping: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _normalize_address(value: object) -> str | None:
    if isinstance(value, str):
        normalized = normalize_text(value)
        return normalized or None
    if not isinstance(value, Mapping):
        return None

    fields = (
        "line1",
        "line2",
        "postal_code",
        "city",
        "region",
        "country_code",
    )
    parts = [
        normalize_text(item)
        for field in fields
        if isinstance((item := value.get(field)), str) and item.strip()
    ]
    return "|".join(parts) if parts else None


def _external_identity_values(value: object) -> frozenset[tuple[str, str]]:
    identities: set[tuple[str, str]] = set()
    for item in _as_items(value):
        if not isinstance(item, Mapping):
            continue
        system = item.get("system")
        external_id = item.get("external_id")
        if isinstance(system, str) and isinstance(external_id, str):
            identities.add(
                (
                    normalize_external_system(system),
                    normalize_external_id(external_id),
                )
            )
    return frozenset(identities)


def _custom_identifier_values(value: object) -> frozenset[tuple[str, str]]:
    if not isinstance(value, Mapping):
        return frozenset()
    identifiers: set[tuple[str, str]] = set()
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            continue
        key = normalize_text(raw_key)
        identifier = unicodedata.normalize("NFKC", raw_value).strip()
        if key and identifier:
            identifiers.add((key, identifier))
    return frozenset(identifiers)


@dataclass(frozen=True, slots=True)
class DedupProfile:
    """Canonical normalized signals extracted from one record mapping."""

    emails: frozenset[str] = frozenset()
    phones: frozenset[str] = frozenset()
    full_name: str | None = None
    organization: str | None = None
    addresses: frozenset[str] = frozenset()
    external_identities: frozenset[tuple[str, str]] = frozenset()
    custom_identifiers: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> DedupProfile:
        """Build a profile from canonical CRM/import field names."""

        raw_emails = _first_non_empty(values, "normalized_email", "email", "emails")
        emails = frozenset(normalize_email(item) for item in _string_values(raw_emails))

        raw_phones = _first_non_empty(values, "normalized_phone", "phone", "phones")
        phones = frozenset(normalize_phone(item) for item in _string_values(raw_phones))

        full_name_value = _first_non_empty(values, "full_name", "display_name")
        full_name: str | None = None
        if isinstance(full_name_value, str) and full_name_value.strip():
            full_name = normalize_text(full_name_value)
        elif isinstance(values.get("first_name"), str) or isinstance(
            values.get("last_name"), str
        ):
            first_name = values.get("first_name")
            last_name = values.get("last_name")
            name_parts = [
                item
                for item in (first_name, last_name)
                if isinstance(item, str) and item.strip()
            ]
            if name_parts:
                full_name = normalize_text(" ".join(name_parts))

        organization_value = _first_non_empty(
            values,
            "organization_id",
            "organization",
            "organization_name",
            "company",
        )
        organization = (
            normalize_text(organization_value)
            if isinstance(organization_value, str) and organization_value.strip()
            else None
        )

        raw_addresses = _first_non_empty(values, "address", "addresses")
        addresses = frozenset(
            normalized
            for item in _as_items(raw_addresses)
            if (normalized := _normalize_address(item)) is not None
        )

        raw_external = _first_non_empty(
            values,
            "external_identity",
            "external_identities",
        )

        return cls(
            emails=emails,
            phones=phones,
            full_name=full_name,
            organization=organization,
            addresses=addresses,
            external_identities=_external_identity_values(raw_external),
            custom_identifiers=_custom_identifier_values(
                values.get("custom_identifiers")
            ),
        )


class StandardSignalMatcher:
    """Match all V0.9 signals using exact normalized equality."""

    def match(
        self,
        incoming: DedupProfile,
        candidate: DedupProfile,
    ) -> tuple[SignalMatch, ...]:
        matches: list[SignalMatch] = []

        for value in sorted(incoming.emails & candidate.emails):
            matches.append(SignalMatch(DedupSignal.EMAIL, value))
        for value in sorted(incoming.phones & candidate.phones):
            matches.append(SignalMatch(DedupSignal.PHONE, value))

        if incoming.full_name and incoming.full_name == candidate.full_name:
            matches.append(
                SignalMatch(DedupSignal.FULL_NAME, incoming.full_name)
            )
        if incoming.organization and incoming.organization == candidate.organization:
            matches.append(
                SignalMatch(DedupSignal.ORGANIZATION, incoming.organization)
            )

        for value in sorted(incoming.addresses & candidate.addresses):
            matches.append(SignalMatch(DedupSignal.ADDRESS, value))

        for system, external_id in sorted(
            incoming.external_identities & candidate.external_identities
        ):
            matches.append(
                SignalMatch(
                    DedupSignal.EXTERNAL_IDENTITY,
                    external_id,
                    key=system,
                )
            )

        for namespace, identifier in sorted(
            incoming.custom_identifiers & candidate.custom_identifiers
        ):
            matches.append(
                SignalMatch(
                    DedupSignal.CUSTOM_IDENTIFIER,
                    identifier,
                    key=namespace,
                )
            )

        return tuple(matches)


__all__ = [
    "DedupProfile",
    "DedupSignal",
    "SignalMatch",
    "StandardSignalMatcher",
    "normalize_text",
]
