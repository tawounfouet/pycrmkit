"""Tag value objects and normalization semantics."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError

_WHITESPACE = re.compile(r"\s+")


def normalize_tag_name(value: str) -> tuple[str, str]:
    """Return display and normalized comparison forms for a tag name."""
    display = _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())
    if not display:
        raise ValidationError("tag name cannot be empty", code="tag.name.required")
    if len(display) > 80:
        raise ValidationError(
            "tag name cannot exceed 80 characters",
            code="tag.name.too_long",
        )
    return display, display.casefold()


@dataclass(frozen=True, slots=True)
class TagName(ValueObject):
    """Human tag label with deterministic normalized equality/search value."""

    value: str
    normalized: str = field(init=False)

    def __post_init__(self) -> None:
        value, normalized = normalize_tag_name(self.value)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "normalized", normalized)

    def __str__(self) -> str:
        return self.value
