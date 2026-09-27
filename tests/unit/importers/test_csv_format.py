"""CSV import/export format behavior."""

from __future__ import annotations

from io import StringIO

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.exporters import CSVExporter
from pycrmkit.importers import CSVReader, ImportReader


def test_csv_reader_supports_unicode_missing_values_and_protocol() -> None:
    source = StringIO("email,name,city\nada@example.com,Ada,Paris\nzoe@example.com,Zoé,\n")
    reader = CSVReader(source)

    assert isinstance(reader, ImportReader)
    assert list(reader.read()) == [
        {"email": "ada@example.com", "name": "Ada", "city": "Paris"},
        {"email": "zoe@example.com", "name": "Zoé", "city": ""},
    ]


def test_csv_empty_input_yields_no_rows() -> None:
    assert list(CSVReader(StringIO("")).read()) == []


def test_csv_rejects_duplicate_headers_and_extra_columns() -> None:
    with pytest.raises(ValidationError) as duplicate:
        list(CSVReader(StringIO("email,email\na@example.com,b@example.com\n")).read())
    assert duplicate.value.code == "import.csv.header.duplicate"

    with pytest.raises(ValidationError) as extra:
        list(CSVReader(StringIO("email,name\na@example.com,Ada,extra\n")).read())
    assert extra.value.code == "import.csv.columns.extra"


def test_csv_export_round_trip_preserves_row_order_and_duplicates() -> None:
    destination = StringIO()
    records = [
        {"email": "ada@example.com", "name": "Ada Lovelace"},
        {"email": "ada@example.com", "name": "Ada Lovelace"},
        {"email": "zoe@example.com", "name": "Zoé"},
    ]

    count = CSVExporter(destination).write(records)
    destination.seek(0)

    assert count == 3
    assert list(CSVReader(destination).read()) == records


def test_csv_export_rejects_nested_values() -> None:
    with pytest.raises(ValidationError) as error:
        CSVExporter(StringIO()).write(({"email": "ada@example.com", "custom": {"tier": 1}},))

    assert error.value.code == "export.csv.value.invalid"


def test_csv_path_round_trip(tmp_path) -> None:
    path = tmp_path / "contacts.csv"
    records = ({"email": "ada@example.com", "active": True},)

    assert CSVExporter(path).write(records) == 1
    assert list(CSVReader(path).read()) == [{"email": "ada@example.com", "active": "True"}]
