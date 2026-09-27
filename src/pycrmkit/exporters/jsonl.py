"""JSON Lines exporter for provider-neutral CRM records."""

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
class JSONLExporter:
    """Write one JSON object per line."""

    destination: TextDestination
    encoding: str = "utf-8"
    ensure_ascii: bool = False

    def write(self, records: Iterable[Mapping[str, object]]) -> int:
        """Write records and return the number of lines emitted."""

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
        count = 0

        for record in records:
            try:
                encoded = encoder.encode(dict(record))
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    "JSONL export record contains a non-serializable value",
                    code="export.jsonl.value.invalid",
                    context={"row": count + 1},
                ) from exc

            stream.write(encoded)
            stream.write("\n")
            count += 1

        return count


__all__ = ["JSONLExporter", "TextDestination"]
