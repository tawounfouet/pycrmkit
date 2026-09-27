"""JSON Lines import/export format behavior."""

from __future__ import annotations

from io import StringIO

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.exporters import JSONLExporter
from pycrmkit.importers import ImportReader, JSONLReader


def test_jsonl_reader_skips_blank_lines_and_preserves_unicode() -> None:
    source = StringIO(
        '{"email":"ada@example.com","name":"Ada"}\n\n'
        '{"email":"zoe@example.com","name":"Zoé"}\n'
    )
    reader = JSONLReader(source)

    assert isinstance(reader, ImportReader)
    assert list(reader.read()) == [
        {"email": "ada@example.com", "name": "Ada"},
        {"email": "zoe@example.com", "name": "Zoé"},
    ]


def test_jsonl_rejects_invalid_line_without_silent_skipping() -> None:
    source = StringIO(
        '{"email":"ada@example.com"}\n'
        '{"email":}\n'
        '{"email":"zoe@example.com"}\n'
    )

    with pytest.raises(ValidationError) as error:
        list(JSONLReader(source).read())

    assert error.value.code == "import.jsonl.syntax.invalid"
    assert error.value.context["line"] == 2


def test_jsonl_export_round_trip_is_stream_friendly_for_large_batches() -> None:
    destination = StringIO()
    records = [
        {"index": index, "email": f"user-{index}@example.com"}
        for index in range(1000)
    ]

    count = JSONLExporter(destination).write(iter(records))
    destination.seek(0)
    loaded = list(JSONLReader(destination).read())

    assert count == 1000
    assert loaded == records


def test_jsonl_preserves_duplicate_rows() -> None:
    destination = StringIO()
    duplicate = {"email": "duplicate@example.com", "custom": {"source": "crm"}}

    JSONLExporter(destination).write((duplicate, duplicate))
    destination.seek(0)

    assert list(JSONLReader(destination).read()) == [duplicate, duplicate]


def test_jsonl_export_rejects_non_serializable_values() -> None:
    with pytest.raises(ValidationError) as error:
        JSONLExporter(StringIO()).write(({"values": {1, 2}},))

    assert error.value.code == "export.jsonl.value.invalid"


def test_jsonl_path_round_trip(tmp_path) -> None:
    path = tmp_path / "contacts.jsonl"
    records = ({"email": "ada@example.com"}, {"email": "zoe@example.com"})

    assert JSONLExporter(path).write(records) == 2
    assert list(JSONLReader(path).read()) == list(records)
