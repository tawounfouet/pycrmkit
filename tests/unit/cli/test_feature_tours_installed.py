"""AUD-FIX-06: packaged tours must not rely on the source repository."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

from pycrmkit._feature_tours_loader import TOUR_FILES, load_tour, run_tour
from pycrmkit.cli.commands.tours import TOURS


def test_cli_catalog_matches_packaged_allowlist() -> None:
    assert tuple(filename for filename, _ in TOURS) == TOUR_FILES


@pytest.mark.parametrize("filename", TOUR_FILES)
def test_each_packaged_tour_is_importable(filename: str) -> None:
    resource = resources.files("pycrmkit").joinpath("_feature_tours", f"{filename}.txt")
    assert resource.is_file()
    module = load_tour(filename)
    assert callable(getattr(module, "run_tour", None))


@pytest.mark.parametrize("filename", TOUR_FILES)
def test_packaged_tour_runs_outside_checkout(
    filename: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = run_tour(filename)
    assert isinstance(result, dict)


@pytest.mark.parametrize("bad", ["../evil.py", "/tmp/evil.py", "unknown.py", "", "01_core_crm.py.txt"])
def test_unknown_tours_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="Unknown or unsupported"):
        load_tour(bad)
