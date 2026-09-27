"""JSON Lines reader adapter for the provider-neutral import pipeline."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TextIO

from pycrmkit.exceptions import ValidationError

TextSource = str | PathLike[str] | TextIO


@dataclass(slots=True)
class JSONLReader:
    """Read one JSON object per non-blank line."""

    source: TextSource
    encoding: str = "utf-8"

    def read(self) -> Iterator[Mapping[str, object]]:
        """Yield JSONL records while preserving source order."""

        if isinstance(self.source, (str, PathLike)):
            with Path(self.source).open("r", encoding=self.encoding) as stream:
                yield from self._read_stream(stream)
            return

        yield from self._read_stream(self.source)

    def _read_stream(self, stream: TextIO) -> Iterator[Mapping[str, object]]:
        for source_line, line in enumerate(stream, start=1):
            if not line.strip():
                continue

            try:
                value: object = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    "JSONL line is not syntactically valid JSON",
                    code="import.jsonl.syntax.invalid",
                    context={
                        "line": source_line,
                        "column": exc.colno,
                    },
                ) from exc

            if not isinstance(value, dict):
                raise ValidationError(
                    "JSONL records must be JSON objects",
                    code="import.jsonl.row.invalid",
                    context={"line": source_line},
                )
            if not all(isinstance(key, str) for key in value):
                raise ValidationError(
                    "JSONL object keys must be strings",
                    code="import.jsonl.key.invalid",
                    context={"line": source_line},
                )
            yield dict(value)


__all__ = ["JSONLReader", "TextSource"]
