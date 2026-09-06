"""Minimal installed-package smoke test."""

from __future__ import annotations

import pycrmkit


def main() -> None:
    version = pycrmkit.__version__
    if not version:
        raise SystemExit("PyCRMKit version is empty")
    print(f"PyCRMKit {version}: smoke OK")


if __name__ == "__main__":
    main()
