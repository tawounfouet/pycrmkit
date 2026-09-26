"""Import normalization behavior."""

from __future__ import annotations

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.importers import (
    ImportRow,
    NormalizationRule,
    RecordNormalizer,
    casefold_text,
    compose_normalizers,
    empty_text_to_none,
    strip_text,
)


def test_record_normalizer_applies_rules_in_declaration_order() -> None:
    row = ImportRow(
        1,
        {
            "email": "  Ada@Example.COM  ",
            "note": "   ",
            "count": 2,
        },
    )
    normalizer = RecordNormalizer(
        (
            NormalizationRule(
                "email",
                compose_normalizers(strip_text, casefold_text),
            ),
            NormalizationRule("note", empty_text_to_none),
        )
    )

    normalized = normalizer.normalize(row)

    assert normalized.values == {
        "email": "ada@example.com",
        "note": None,
        "count": 2,
    }


def test_normalization_failure_becomes_typed_validation_error() -> None:
    row = ImportRow(3, {"email": 42})
    normalizer = RecordNormalizer((NormalizationRule("email", strip_text),))

    with pytest.raises(ValidationError) as error:
        normalizer.normalize(row)

    assert error.value.code == "import.normalization.failed"
    assert error.value.context == {"row": 3, "field": "email"}
