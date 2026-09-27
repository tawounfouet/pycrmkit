"""Conflict detection for conservative duplicate decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pycrmkit.dedup.matchers import DedupProfile, DedupSignal


class ConflictSeverity(StrEnum):
    """Whether contradictory evidence should block auto-deduplication."""

    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class DedupConflict:
    """Contradictory evidence between incoming and candidate records."""

    signal: DedupSignal
    severity: ConflictSeverity
    key: str | None = None
    incoming_values: tuple[str, ...] = ()
    candidate_values: tuple[str, ...] = ()


def _namespace_map(
    values: frozenset[tuple[str, str]],
) -> dict[str, frozenset[str]]:
    output: dict[str, set[str]] = {}
    for namespace, identifier in values:
        output.setdefault(namespace, set()).add(identifier)
    return {key: frozenset(items) for key, items in output.items()}


class StandardConflictDetector:
    """Detect contradictory signals without trying to resolve them."""

    def detect(
        self,
        incoming: DedupProfile,
        candidate: DedupProfile,
    ) -> tuple[DedupConflict, ...]:
        conflicts: list[DedupConflict] = []

        if incoming.emails and candidate.emails and not (
            incoming.emails & candidate.emails
        ):
            conflicts.append(
                DedupConflict(
                    DedupSignal.EMAIL,
                    ConflictSeverity.WARNING,
                    incoming_values=tuple(sorted(incoming.emails)),
                    candidate_values=tuple(sorted(candidate.emails)),
                )
            )

        if incoming.phones and candidate.phones and not (
            incoming.phones & candidate.phones
        ):
            conflicts.append(
                DedupConflict(
                    DedupSignal.PHONE,
                    ConflictSeverity.WARNING,
                    incoming_values=tuple(sorted(incoming.phones)),
                    candidate_values=tuple(sorted(candidate.phones)),
                )
            )

        if (
            incoming.full_name
            and candidate.full_name
            and incoming.full_name != candidate.full_name
        ):
            conflicts.append(
                DedupConflict(
                    DedupSignal.FULL_NAME,
                    ConflictSeverity.WARNING,
                    incoming_values=(incoming.full_name,),
                    candidate_values=(candidate.full_name,),
                )
            )

        if (
            incoming.organization
            and candidate.organization
            and incoming.organization != candidate.organization
        ):
            conflicts.append(
                DedupConflict(
                    DedupSignal.ORGANIZATION,
                    ConflictSeverity.WARNING,
                    incoming_values=(incoming.organization,),
                    candidate_values=(candidate.organization,),
                )
            )

        incoming_external = _namespace_map(incoming.external_identities)
        candidate_external = _namespace_map(candidate.external_identities)
        for namespace in sorted(incoming_external.keys() & candidate_external.keys()):
            left = incoming_external[namespace]
            right = candidate_external[namespace]
            if not left & right:
                conflicts.append(
                    DedupConflict(
                        DedupSignal.EXTERNAL_IDENTITY,
                        ConflictSeverity.WARNING,
                        key=namespace,
                        incoming_values=tuple(sorted(left)),
                        candidate_values=tuple(sorted(right)),
                    )
                )

        incoming_custom = _namespace_map(incoming.custom_identifiers)
        candidate_custom = _namespace_map(candidate.custom_identifiers)
        for namespace in sorted(incoming_custom.keys() & candidate_custom.keys()):
            left = incoming_custom[namespace]
            right = candidate_custom[namespace]
            if not left & right:
                conflicts.append(
                    DedupConflict(
                        DedupSignal.CUSTOM_IDENTIFIER,
                        ConflictSeverity.BLOCKING,
                        key=namespace,
                        incoming_values=tuple(sorted(left)),
                        candidate_values=tuple(sorted(right)),
                    )
                )

        return tuple(conflicts)


__all__ = [
    "ConflictSeverity",
    "DedupConflict",
    "StandardConflictDetector",
]
