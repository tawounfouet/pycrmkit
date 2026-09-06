"""Organization value objects and normalization rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError

_WHITESPACE = re.compile(r"\s+")
_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _clean_text(value: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())


def normalize_domain(value: str) -> str:
    """Normalize a DNS domain without accepting URLs, paths, or email addresses."""
    cleaned = _clean_text(value).rstrip(".")
    if not cleaned or any(token in cleaned for token in ("://", "/", "@")):
        raise ValidationError(
            "domain must be a bare DNS name",
            code="organization.domain.invalid",
            context={"value": value},
        )
    try:
        ascii_domain = cleaned.encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise ValidationError(
            "domain contains invalid internationalized characters",
            code="organization.domain.invalid",
            context={"value": value},
        ) from exc
    if len(ascii_domain) > 253:
        raise ValidationError(
            "domain cannot exceed 253 characters",
            code="organization.domain.invalid_length",
        )
    labels = ascii_domain.split(".")
    if len(labels) < 2 or any(not _DOMAIN_LABEL.fullmatch(label) for label in labels):
        raise ValidationError(
            "domain must contain valid DNS labels and a suffix",
            code="organization.domain.invalid",
            context={"value": value},
        )
    return ascii_domain


@dataclass(frozen=True, slots=True)
class OrganizationDomain(ValueObject):
    """Organization-owned DNS domain with stable comparison semantics."""

    value: str
    is_primary: bool = False
    normalized: str = field(init=False)

    def __post_init__(self) -> None:
        cleaned = _clean_text(self.value).rstrip(".")
        object.__setattr__(self, "value", cleaned)
        object.__setattr__(self, "normalized", normalize_domain(cleaned))


@dataclass(frozen=True, slots=True)
class OrganizationAddress(ValueObject):
    """Organization postal address without geocoding/provider assumptions."""

    line1: str
    city: str
    postal_code: str | None = None
    line2: str | None = None
    region: str | None = None
    country_code: str | None = None
    is_primary: bool = False

    def __post_init__(self) -> None:
        line1 = _clean_text(self.line1)
        city = _clean_text(self.city)
        if not line1 or not city:
            raise ValidationError(
                "address line1 and city are required",
                code="organization.address.invalid",
            )
        object.__setattr__(self, "line1", line1)
        object.__setattr__(self, "city", city)
        for attribute in ("postal_code", "line2", "region"):
            value = getattr(self, attribute)
            object.__setattr__(self, attribute, _clean_text(value) if value else None)
        if self.country_code:
            country_code = _clean_text(self.country_code).upper()
            if len(country_code) != 2 or not country_code.isalpha():
                raise ValidationError(
                    "country_code must be a two-letter ISO-style code",
                    code="organization.address.invalid_country_code",
                    context={"country_code": self.country_code},
                )
            object.__setattr__(self, "country_code", country_code)

    @property
    def formatted(self) -> str:
        """Return a compact human-readable representation."""
        parts = [
            self.line1,
            self.line2,
            self.postal_code,
            self.city,
            self.region,
            self.country_code,
        ]
        return ", ".join(part for part in parts if part)
