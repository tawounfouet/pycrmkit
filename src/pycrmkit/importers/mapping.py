"""Field mapping for provider-neutral imports."""

from __future__ import annotations

from dataclasses import dataclass, field

from pycrmkit.exceptions import ValidationError
from pycrmkit.importers.base import ImportRow

_MISSING = object()


def _field_name(value: str, *, role: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValidationError(
            f"{role} field name cannot be empty",
            code="import.mapping.field.empty",
            context={"role": role},
        )
    return normalized


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """Map one source field to a target field, optionally with a default."""

    source: str
    target: str | None = None
    default: object = field(default=_MISSING, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _field_name(self.source, role="source"))
        if self.target is not None:
            object.__setattr__(self, "target", _field_name(self.target, role="target"))

    @property
    def destination(self) -> str | None:
        """Return the effective output field; None means explicitly ignored."""

        return self.target

    @property
    def has_default(self) -> bool:
        return self.default is not _MISSING


@dataclass(frozen=True, slots=True)
class RecordMapper:
    """Apply explicit source-to-target field rules to one import row."""

    mappings: tuple[FieldMapping, ...]
    preserve_unmapped: bool = False

    def __post_init__(self) -> None:
        destinations = [
            mapping.destination
            for mapping in self.mappings
            if mapping.destination is not None
        ]
        if len(destinations) != len(set(destinations)):
            raise ValidationError(
                "multiple import field mappings target the same field",
                code="import.mapping.target.duplicate",
            )

    def map(self, row: ImportRow) -> ImportRow:
        source_values = row.values
        output: dict[str, object] = (
            dict(source_values) if self.preserve_unmapped else {}
        )

        for mapping in self.mappings:
            destination = mapping.destination
            if destination is None:
                output.pop(mapping.source, None)
                continue

            if mapping.source in source_values:
                output[destination] = source_values[mapping.source]
                if self.preserve_unmapped and destination != mapping.source:
                    output.pop(mapping.source, None)
                continue

            if mapping.has_default:
                output[destination] = mapping.default

        return row.replace(output)


__all__ = ["FieldMapping", "RecordMapper"]
