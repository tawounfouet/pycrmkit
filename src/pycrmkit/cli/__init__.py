"""Command-line interface package for PyCRMKit."""

from __future__ import annotations

from pycrmkit.cli.bootstrap import main
from pycrmkit.cli.exit_codes import ExitCode

__all__ = ["main", "ExitCode"]
