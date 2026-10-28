"""Provider-neutral input safeguards shared by optional Campaign transports.

These checks protect HTTP boundaries only. They do not redefine Campaign domain
invariants or require FastAPI/Django to be present in the core installation.
"""

from __future__ import annotations

import json
from typing import Any

MAX_CAMPAIGN_METADATA_BYTES = 16_384
MAX_CAMPAIGN_METADATA_DEPTH = 8


def validate_campaign_metadata(value: dict[str, Any]) -> dict[str, Any]:
    """Require finite, bounded JSON metadata before invoking the CRM facade."""
    try:
        serialized = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must contain only finite JSON values") from exc

    if len(serialized.encode("utf-8")) > MAX_CAMPAIGN_METADATA_BYTES:
        raise ValueError("metadata may not exceed 16384 UTF-8 bytes")

    def check_depth(node: object, level: int) -> None:
        if level > MAX_CAMPAIGN_METADATA_DEPTH:
            raise ValueError("metadata nesting depth may not exceed 8")
        if isinstance(node, dict):
            for child in node.values():
                check_depth(child, level + 1)
        elif isinstance(node, list):
            for child in node:
                check_depth(child, level + 1)

    check_depth(value, 0)
    return value


__all__ = [
    "MAX_CAMPAIGN_METADATA_BYTES",
    "MAX_CAMPAIGN_METADATA_DEPTH",
    "validate_campaign_metadata",
]
