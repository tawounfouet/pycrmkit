from pycrmkit import __version__


def test_package_version() -> None:
    assert __version__ == "1.1.0a3"
