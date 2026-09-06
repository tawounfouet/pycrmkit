"""Organization-domain normalization and invariant policies."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from pycrmkit.exceptions import ConflictError, ValidationError
from pycrmkit.organizations.value_objects import OrganizationAddress, OrganizationDomain

_WHITESPACE = re.compile(r"\s+")


def normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional organization text without changing meaningful case."""
    if value is None:
        return None
    normalized = _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())
    return normalized or None


def normalize_required_text(value: str, *, field_name: str) -> str:
    """Normalize required organization text and reject blank values."""
    normalized = normalize_optional_text(value)
    if normalized is None:
        raise ValidationError(
            f"{field_name} is required",
            code=f"organization.{field_name}.required",
        )
    return normalized


def resolve_display_name(
    *,
    legal_name: str,
    trading_name: str | None,
    explicit: str | None,
) -> str:
    """Resolve display name: explicit > trading name > legal name."""
    return (
        normalize_optional_text(explicit)
        or normalize_optional_text(trading_name)
        or normalize_required_text(legal_name, field_name="legal_name")
    )


def validate_organization_domains(domains: Iterable[OrganizationDomain]) -> None:
    """Reject duplicate normalized domains and multiple primary domains."""
    seen: set[str] = set()
    primary = 0
    for domain in domains:
        if domain.normalized in seen:
            raise ConflictError(
                "duplicate domain within organization",
                code="organization.domain.duplicate",
                context={"domain": domain.normalized},
            )
        seen.add(domain.normalized)
        primary += int(domain.is_primary)
    if primary > 1:
        raise ValidationError(
            "an organization cannot have more than one primary domain",
            code="organization.domain.multiple_primary",
        )


def validate_organization_addresses(addresses: Iterable[OrganizationAddress]) -> None:
    """Reject multiple primary organization addresses."""
    if sum(int(address.is_primary) for address in addresses) > 1:
        raise ValidationError(
            "an organization cannot have more than one primary address",
            code="organization.address.multiple_primary",
        )
