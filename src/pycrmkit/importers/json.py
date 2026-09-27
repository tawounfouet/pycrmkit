"""JSON array reader adapter for the provider-neutral import pipeline."""

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
class JSONReader:
    """Read a JSON document whose root is an array of objects."""

    source: TextSource
    encoding: str = "utf-8"

    def read(self) -> Iterator[Mapping[str, object]]:
        """Yield object records from one JSON array document."""

        if isinstance(self.source, (str, PathLike)):
            with Path(self.source).open("r", encoding=self.encoding) as stream:
                yield from self._read_stream(stream)
            return

        yield from self._read_stream(self.source)

    def _read_stream(self, stream: TextIO) -> Iterator[Mapping[str, object]]:
        try:
            document: object = json.load(stream)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                "JSON input is not syntactically valid",
                code="import.json.syntax.invalid",
                context={"line": exc.lineno, "column": exc.colno},
            ) from exc

        if not isinstance(document, list):
            raise ValidationError(
                "JSON import root must be an array of objects",
                code="import.json.root.invalid",
            )

        for row_number, value in enumerate(document, start=1):
            if not isinstance(value, dict):
                raise ValidationError(
                    "JSON array entries must be objects",
                    code="import.json.row.invalid",
                    context={"row": row_number},
                )
            if not all(isinstance(key, str) for key in value):
                raise ValidationError(
                    "JSON object keys must be strings",
                    code="import.json.key.invalid",
                    context={"row": row_number},
                )
            yield dict(value)


__all__ = ["JSONReader", "TextSource"]
