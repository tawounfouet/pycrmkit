"""JSON import/export format behavior."""

from __future__ import annotations

from io import StringIO

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.exporters import JSONExporter
from pycrmkit.importers import ImportReader, JSONReader


def test_json_reader_preserves_unicode_nested_values_and_duplicates() -> None:
    source = StringIO(
        '[{"email":"ada@example.com","name":"Ada","custom":{"tier":1}},'
        '{"email":"ada@example.com","name":"Ada","custom":{"tier":1}},'
        '{"email":"zoe@example.com","name":"Zoé","tags":["vip"]}]'
    )
    reader = JSONReader(source)

    rows = list(reader.read())

    assert isinstance(reader, ImportReader)
    assert rows[0] == {
        "email": "ada@example.com",
        "name": "Ada",
        "custom": {"tier": 1},
    }
    assert rows[1] == rows[0]
    assert rows[2]["name"] == "Zoé"
    assert rows[2]["tags"] == ["vip"]


def test_json_empty_array_yields_no_rows() -> None:
    assert list(JSONReader(StringIO("[]")).read()) == []


def test_json_rejects_invalid_syntax_root_and_non_object_rows() -> None:
    with pytest.raises(ValidationError) as syntax:
        list(JSONReader(StringIO('[{"email":}')).read())
    assert syntax.value.code == "import.json.syntax.invalid"

    with pytest.raises(ValidationError) as root:
        list(JSONReader(StringIO('{"email":"ada@example.com"}')).read())
    assert root.value.code == "import.json.root.invalid"

    with pytest.raises(ValidationError) as row:
        list(JSONReader(StringIO('[{"email":"ada@example.com"},42]')).read())
    assert row.value.code == "import.json.row.invalid"


def test_json_export_round_trip_keeps_nested_json_values() -> None:
    destination = StringIO()
    records = [
        {
            "email": "ada@example.com",
            "name": "Ada Lovelace",
            "external_identity": {"system": "hubspot", "external_id": "42"},
            "custom_fields": {"segment": "R&D"},
        },
        {
            "email": "zoe@example.com",
            "name": "Zoé",
            "tags": ["vip", "équipe"],
        },
    ]

    count = JSONExporter(destination).write(records)
    destination.seek(0)

    assert count == 2
    assert list(JSONReader(destination).read()) == records
    assert "\\u00e9" not in destination.getvalue().casefold()


def test_json_export_rejects_non_serializable_values() -> None:
    with pytest.raises(ValidationError) as error:
        JSONExporter(StringIO()).write(({"values": {1, 2}},))

    assert error.value.code == "export.json.value.invalid"


def test_json_path_round_trip(tmp_path) -> None:
    path = tmp_path / "contacts.json"
    records = ({"email": "ada@example.com", "score": 3},)

    assert JSONExporter(path).write(records) == 1
    assert list(JSONReader(path).read()) == list(records)
