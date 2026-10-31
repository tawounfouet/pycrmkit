"""Current checkout identity is consistent with installed distribution metadata."""

from importlib.metadata import version

from pycrmkit import __version__


def test_package_version() -> None:
    assert __version__ == "1.3.0.dev0"
    assert version("pycrmkit") == __version__
