"""CSV exporter for provider-neutral CRM records."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from itertools import chain
from os import PathLike
from pathlib import Path
from typing import TextIO
from uuid import UUID

from pycrmkit.exceptions import ValidationError

TextDestination = str | PathLike[str] | TextIO
CSVScalar = str | int | float | bool | Decimal | date | datetime | UUID | None


def _validate_fieldnames(fieldnames: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(fieldnames)
    if not normalized or any(not field.strip() for field in normalized):
        raise ValidationError(
            "CSV export field names must be non-empty",
            code="export.csv.header.invalid",
        )
    if len(normalized) != len(set(normalized)):
        raise ValidationError(
            "CSV export field names must be unique",
            code="export.csv.header.duplicate",
        )
    return normalized


def _cell(value: object, *, field: str) -> CSVScalar:
    if value is None or isinstance(
        value,
        (str, int, float, bool, Decimal, date, datetime, UUID),
    ):
        return value
    raise ValidationError(
        "CSV export values must be scalar",
        code="export.csv.value.invalid",
        context={"field": field, "type": type(value).__name__},
    )


@dataclass(slots=True)
class CSVExporter:
    """Write mapping-shaped records as CSV."""

    destination: TextDestination
    fieldnames: Sequence[str] | None = None
    encoding: str = "utf-8"
    delimiter: str = ","
    lineterminator: str = "\n"

    def __post_init__(self) -> None:
        if len(self.delimiter) != 1:
            raise ValidationError(
                "CSV delimiter must be exactly one character",
                code="export.csv.delimiter.invalid",
                context={"delimiter": self.delimiter},
            )
        if self.fieldnames is not None:
            self.fieldnames = _validate_fieldnames(self.fieldnames)

    def write(self, records: Iterable[Mapping[str, object]]) -> int:
        """Write records and return the number of data rows emitted."""

        if isinstance(self.destination, (str, PathLike)):
            with Path(self.destination).open(
                "w",
                encoding=self.encoding,
                newline="",
            ) as stream:
                return self._write_stream(stream, records)

        return self._write_stream(self.destination, records)

    def _write_stream(
        self,
        stream: TextIO,
        records: Iterable[Mapping[str, object]],
    ) -> int:
        iterator = iter(records)
        try:
            first = next(iterator)
        except StopIteration:
            if self.fieldnames is None:
                return 0
            writer = csv.DictWriter(
                stream,
                fieldnames=self.fieldnames,
                delimiter=self.delimiter,
                lineterminator=self.lineterminator,
            )
            writer.writeheader()
            return 0

        fields = (
            _validate_fieldnames(tuple(first.keys()))
            if self.fieldnames is None
            else tuple(self.fieldnames)
        )
        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            delimiter=self.delimiter,
            lineterminator=self.lineterminator,
        )
        writer.writeheader()

        count = 0
        allowed = set(fields)
        for row_number, record in enumerate(chain((first,), iterator), start=1):
            extras = set(record) - allowed
            if extras:
                raise ValidationError(
                    "CSV export record contains fields outside the header",
                    code="export.csv.fields.unexpected",
                    context={
                        "row": row_number,
                        "fields": tuple(sorted(extras)),
                    },
                )

            encoded = {
                field: _cell(record.get(field), field=field)
                for field in fields
            }
            writer.writerow(encoded)
            count += 1

        return count


__all__ = ["CSVExporter", "CSVScalar", "TextDestination"]
