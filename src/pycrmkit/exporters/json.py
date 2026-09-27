"""Streaming JSON array exporter for provider-neutral CRM records."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TextIO

from pycrmkit.exceptions import ValidationError

TextDestination = str | PathLike[str] | TextIO


@dataclass(slots=True)
class JSONExporter:
    """Write mapping-shaped records as a JSON array without buffering all rows."""

    destination: TextDestination
    encoding: str = "utf-8"
    ensure_ascii: bool = False

    def write(self, records: Iterable[Mapping[str, object]]) -> int:
        """Write records and return the number of objects emitted."""

        if isinstance(self.destination, (str, PathLike)):
            with Path(self.destination).open("w", encoding=self.encoding) as stream:
                return self._write_stream(stream, records)

        return self._write_stream(self.destination, records)

    def _write_stream(
        self,
        stream: TextIO,
        records: Iterable[Mapping[str, object]],
    ) -> int:
        encoder = json.JSONEncoder(
            ensure_ascii=self.ensure_ascii,
            separators=(",", ":"),
        )
        stream.write("[")
        count = 0

        for record in records:
            try:
                encoded = encoder.encode(dict(record))
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    "JSON export record contains a non-serializable value",
                    code="export.json.value.invalid",
                    context={"row": count + 1},
                ) from exc

            if count:
                stream.write(",")
            stream.write(encoded)
            count += 1

        stream.write("]\n")
        return count


__all__ = ["JSONExporter", "TextDestination"]
