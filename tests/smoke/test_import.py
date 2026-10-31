def test_import_pycrmkit() -> None:
    import pycrmkit

    assert pycrmkit.__version__ == "1.3.0.dev0"
