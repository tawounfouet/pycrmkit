"""Import mapping behavior."""

from __future__ import annotations

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.importers import FieldMapping, ImportRow, RecordMapper


def test_record_mapper_renames_defaults_ignores_and_preserves_unmapped_fields() -> None:
    row = ImportRow(
        1,
        {
            "Email": "Ada@Example.com",
            "Display Name": "Ada Lovelace",
            "ignored": "provider-only",
            "country": "GB",
        },
    )
    mapper = RecordMapper(
        (
            FieldMapping("Email", "email"),
            FieldMapping("Display Name", "display_name"),
            FieldMapping("source", "source", default="legacy_crm"),
            FieldMapping("ignored", None),
        ),
        preserve_unmapped=True,
    )

    mapped = mapper.map(row)

    assert mapped.number == 1
    assert mapped.values == {
        "email": "Ada@Example.com",
        "display_name": "Ada Lovelace",
        "source": "legacy_crm",
        "country": "GB",
    }


def test_record_mapper_without_preservation_outputs_only_declared_targets() -> None:
    row = ImportRow(2, {"email_address": "ada@example.com", "provider_note": "x"})
    mapper = RecordMapper((FieldMapping("email_address", "email"),))

    assert mapper.map(row).values == {"email": "ada@example.com"}


def test_record_mapper_rejects_duplicate_target_configuration() -> None:
    with pytest.raises(ValidationError) as error:
        RecordMapper(
            (
                FieldMapping("primary_email", "email"),
                FieldMapping("secondary_email", "email"),
            )
        )

    assert error.value.code == "import.mapping.target.duplicate"
