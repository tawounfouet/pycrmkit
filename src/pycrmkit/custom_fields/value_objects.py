"""Custom-field types, options, and stable key normalization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
import unicodedata

from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError

_KEY_SEPARATORS = re.compile(r"[\s-]+")
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_OPTION_SEPARATORS = re.compile(r"[\s_-]+")
_OPTION_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_WHITESPACE = re.compile(r"\s+")


def normalize_custom_field_key(value: str) -> str:
    """Normalize a stable custom-field key."""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    key = _KEY_SEPARATORS.sub("_", normalized)
    if not _KEY_PATTERN.fullmatch(key):
        raise ValidationError(
            "custom field key must be a stable lowercase identifier",
            code="custom_field.key.invalid",
            context={"key": value},
        )
    return key


def normalize_option_code(value: str) -> str:
    """Normalize enum option codes into lowercase hyphenated identifiers."""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    code = _OPTION_SEPARATORS.sub("-", normalized)
    if not _OPTION_PATTERN.fullmatch(code):
        raise ValidationError(
            "custom field option code is invalid",
            code="custom_field.option.invalid_code",
            context={"code": value},
        )
    return code


class CustomFieldType(StrEnum):
    """Supported V0.1 custom-field value types."""

    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    ENUM = "enum"
    MULTI_ENUM = "multi_enum"
    REFERENCE = "reference"
    JSON = "json"


@dataclass(frozen=True, slots=True)
class CustomFieldOption(ValueObject):
    """One allowed value for enum and multi-enum definitions."""

    code: str
    label: str

    def __post_init__(self) -> None:
        code = normalize_option_code(self.code)
        label = _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", self.label).strip())
        if not label:
            raise ValidationError(
                "custom field option label cannot be empty",
                code="custom_field.option.label_required",
            )
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "label", label)
