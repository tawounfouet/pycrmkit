"""Explicitly isolate frozen 1.2.0 promotion evidence from development testing.

Only the listed legacy promotion/evidence tests are skipped when checking out
1.3.0 development sources. Stable behavior and compatibility tests continue
to run. The historical suite must be replayed from the immutable v1.2.0 tag.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pycrmkit import __version__

FROZEN_STABLE_PROMOTION = frozenset(
    {
        "test_campaign_stable_version_promotion.py",
        "test_campaign_stable_documentation_gate.py",
        "test_campaign_stable_go_no_go_gate.py",
        "test_rc1_version_alignment.py",
        "test_stable_baseline_scope_freeze.py",
    }
)

ARCHIVAL_REASON = (
    "Archived 1.2.0 promotion/provenance gate; replay against immutable "
    "v1.2.0 tag, not 1.3.0 development checkout"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Show explicit SKIP counts for provenance-only tests on dev source."""
    if __version__ == "1.2.0":
        return
    for item in items:
        if Path(str(item.path)).name in FROZEN_STABLE_PROMOTION:
            item.add_marker(pytest.mark.skip(reason=ARCHIVAL_REASON))
