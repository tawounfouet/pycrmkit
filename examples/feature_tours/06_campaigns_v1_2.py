"""Source-checkout wrapper for installed PyCRMKit feature tour 06_campaigns_v1_2.py.

The executable implementation is shipped inside pycrmkit as package data.
"""

from __future__ import annotations

from pycrmkit._feature_tours_loader import run_tour as _run_packaged_tour


def run_tour() -> object:
    """Execute the canonical packaged tour, preserving the source example entrypoint."""
    return _run_packaged_tour("06_campaigns_v1_2.py")


if __name__ == "__main__":
    run_tour()
