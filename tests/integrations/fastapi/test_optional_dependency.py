"""The core package must not import FastAPI transitively."""

from __future__ import annotations

import subprocess
import sys


def test_core_import_does_not_require_fastapi() -> None:
    script = r"""
import builtins

real_import = builtins.__import__


def guarded(name, *args, **kwargs):
    if name == "fastapi" or name.startswith("fastapi."):
        raise AssertionError("core import attempted to import FastAPI")
    return real_import(name, *args, **kwargs)


builtins.__import__ = guarded
import pycrmkit
assert pycrmkit.__version__
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
