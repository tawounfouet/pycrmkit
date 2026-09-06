"""Contact value objects and normalization rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError

_WHITESPACE = re.compile(r"\s+")
_PHONE_SEPARATORS = re.compile(r"[\s().\-/]+")


def _clean_text(value: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())


def normalize_email(value: str) -> str:
    """Normalize an email for CRM equality/search without provider-specific rewriting."""
    cleaned = _clean_text(value)
    if cleaned.count("@") != 1 or any(character.isspace() for character in cleaned):
        raise ValidationError(
            "email must contain one @ and no whitespace",
            code="contact.email.invalid",
            context={"value": value},
        )
    local, domain = cleaned.rsplit("@", 1)
    if not local or not domain or domain.startswith(".") or domain.endswith("."):
        raise ValidationError(
            "email local-part and domain are required",
            code="contact.email.invalid",
            context={"value": value},
        )
    return f"{local.casefold()}@{domain.casefold()}"


def normalize_phone(value: str) -> str:
    """Normalize separators while deliberately avoiding country-code inference."""
    cleaned = _clean_text(value)
    if not cleaned:
        raise ValidationError("phone cannot be empty", code="contact.phone.invalid")
    if cleaned.startswith("+"):
        body = cleaned[1:]
        prefix = "+"
    else:
        body = cleaned
        prefix = ""
    compact = _PHONE_SEPARATORS.sub("", body)
    if not compact.isdigit():
        raise ValidationError(
            "phone may only contain digits, common separators, and an optional leading +",
            code="contact.phone.invalid",
            context={"value": value},
        )
    if not 3 <= len(compact) <= 20:
        raise ValidationError(
            "phone must contain between 3 and 20 digits",
            code="contact.phone.invalid_length",
            context={"digits": len(compact)},
        )
    if prefix and len(compact) > 15:
        raise ValidationError(
            "international phone numbers cannot exceed 15 digits",
            code="contact.phone.invalid_length",
            context={"digits": len(compact)},
        )
    return f"{prefix}{compact}"


class VerificationState(StrEnum):
    """Provider-independent verification state foundation for contact points."""
    UNKNOWN = "unknown"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ContactEmail(ValueObject):
    """Email address with normalized CRM comparison value."""
    value: str
    is_primary: bool = False
    verification: VerificationState = VerificationState.UNKNOWN
    normalized: str = field(init=False)

    def __post_init__(self) -> None:
        cleaned = _clean_text(self.value)
        object.__setattr__(self, "value", cleaned)
        object.__setattr__(self, "normalized", normalize_email(cleaned))


@dataclass(frozen=True, slots=True)
class ContactPhone(ValueObject):
    """Phone number with a stable normalized comparison value."""
    value: str
    is_primary: bool = False
    verification: VerificationState = VerificationState.UNKNOWN
    normalized: str = field(init=False)

    def __post_init__(self) -> None:
        cleaned = _clean_text(self.value)
        object.__setattr__(self, "value", cleaned)
        object.__setattr__(self, "normalized", normalize_phone(cleaned))


@dataclass(frozen=True, slots=True)
class Address(ValueObject):
    """Postal address without provider-specific geocoding assumptions."""
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
            raise ValidationError("address line1 and city are required", code="contact.address.invalid")
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
                    code="contact.address.invalid_country_code",
                    context={"country_code": self.country_code},
                )
            object.__setattr__(self, "country_code", country_code)

    @property
    def formatted(self) -> str:
        """Return a compact human-readable representation."""
        parts = [self.line1, self.line2, self.postal_code, self.city, self.region, self.country_code]
        return ", ".join(part for part in parts if part)
