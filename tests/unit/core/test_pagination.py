import pytest

from pycrmkit.core import OffsetPageRequest, Page
from pycrmkit.exceptions import ValidationError


def test_offset_page_request_validates_bounds() -> None:
    assert OffsetPageRequest(limit=25, offset=10).limit == 25
    with pytest.raises(ValidationError, match="limit"):
        OffsetPageRequest(limit=0)
    with pytest.raises(ValidationError, match="offset"):
        OffsetPageRequest(offset=-1)


def test_page_navigation_metadata() -> None:
    first = Page(items=(1, 2), limit=2, offset=0, total=3)
    second = Page(items=(3,), limit=2, offset=2, total=3)
    assert first.has_next is True
    assert first.has_previous is False
    assert second.has_next is False
    assert second.has_previous is True
