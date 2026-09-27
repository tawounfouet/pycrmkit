"""CSV reader adapter for the provider-neutral import pipeline."""

from __future__ import annotations

import csv
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TextIO

from pycrmkit.exceptions import ValidationError

TextSource = str | PathLike[str] | TextIO


@dataclass(slots=True)
class CSVReader:
    """Read RFC-4180-style tabular records as mappings."""

    source: TextSource
    encoding: str = "utf-8-sig"
    delimiter: str = ","

    def __post_init__(self) -> None:
        if len(self.delimiter) != 1:
            raise ValidationError(
                "CSV delimiter must be exactly one character",
                code="import.csv.delimiter.invalid",
                context={"delimiter": self.delimiter},
            )

    def read(self) -> Iterator[Mapping[str, object]]:
        """Yield CSV rows in source order."""

        if isinstance(self.source, (str, PathLike)):
            with Path(self.source).open(
                "r",
                encoding=self.encoding,
                newline="",
            ) as stream:
                yield from self._read_stream(stream)
            return

        yield from self._read_stream(self.source)

    def _read_stream(self, stream: TextIO) -> Iterator[Mapping[str, object]]:
        reader = csv.DictReader(stream, delimiter=self.delimiter)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            return

        normalized_fields: list[str] = []
        for field in fieldnames:
            if field is None or not field.strip():
                raise ValidationError(
                    "CSV headers must contain non-empty field names",
                    code="import.csv.header.invalid",
                )
            normalized_fields.append(field)

        if len(normalized_fields) != len(set(normalized_fields)):
            raise ValidationError(
                "CSV headers must be unique",
                code="import.csv.header.duplicate",
                context={"fieldnames": tuple(normalized_fields)},
            )

        for source_line, raw_row in enumerate(reader, start=2):
            extras = raw_row.get(None)
            if extras:
                raise ValidationError(
                    "CSV row contains more columns than the header",
                    code="import.csv.columns.extra",
                    context={"line": source_line},
                )

            row: dict[str, object] = {}
            for key in normalized_fields:
                row[key] = raw_row.get(key)
            yield row


__all__ = ["CSVReader", "TextSource"]
