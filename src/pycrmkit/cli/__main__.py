"""Module entrypoint for python -m pycrmkit.cli."""

from __future__ import annotations

import sys

from pycrmkit.cli.bootstrap import main

if __name__ == "__main__":
    sys.exit(main())
