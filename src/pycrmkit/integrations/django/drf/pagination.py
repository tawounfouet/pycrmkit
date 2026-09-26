"""DRF bridge for PyCRMKit's stable offset pagination contract."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rest_framework import serializers

from pycrmkit.core.pagination import OffsetPageRequest, Page


if TYPE_CHECKING:
    class _SerializerBase(serializers.Serializer[Any]):
        pass
else:
    _SerializerBase = serializers.Serializer


class PaginationQuerySerializer(_SerializerBase):
    """Validate query parameters without changing core pagination semantics."""

    limit = serializers.IntegerField(
        required=False,
        default=OffsetPageRequest.DEFAULT_LIMIT,
        min_value=1,
        max_value=OffsetPageRequest.MAX_LIMIT,
    )
    offset = serializers.IntegerField(required=False, default=0, min_value=0)

    def to_domain(self) -> OffsetPageRequest:
        data = cast(dict[str, Any], self.validated_data)
        return OffsetPageRequest(
            limit=cast(int, data["limit"]),
            offset=cast(int, data["offset"]),
        )


def page_payload(page: Page[Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    """Serialize exact offset metadata consistently with other HTTP adapters."""

    return {
        "items": items,
        "limit": page.limit,
        "offset": page.offset,
        "total": page.total,
        "has_next": page.has_next,
        "has_previous": page.has_previous,
    }


__all__ = ["PaginationQuerySerializer", "page_payload"]
