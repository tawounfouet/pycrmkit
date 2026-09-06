"""Value-object conventions for the PyCRMKit domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValueObject:
    """Marker base for immutable value-semantic domain objects.

    Subclasses should also be declared as frozen dataclasses.
    """
