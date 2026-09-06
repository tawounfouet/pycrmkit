"""Run the PyCRMKit foundation release gate."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*command: str) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    run(sys.executable, "-m", "pytest")
    run("ruff", "check", ".")
    run("ruff", "format", "--check", ".")
    run("mypy", "src/pycrmkit")
    run("mkdocs", "build", "--strict")

    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    run(sys.executable, "-m", "build")
    artifacts = sorted((ROOT / "dist").iterdir())
    if not artifacts:
        raise SystemExit("No distributions were built")
    run(sys.executable, "-m", "twine", "check", *(str(path) for path in artifacts))

    wheels = [path for path in artifacts if path.suffix == ".whl"]
    if len(wheels) != 1:
        raise SystemExit(f"Expected exactly one wheel, found {len(wheels)}")

    with tempfile.TemporaryDirectory(prefix="pycrmkit-release-") as tmp:
        venv = Path(tmp) / "venv"
        run(sys.executable, "-m", "venv", str(venv))
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        run(str(python), "-m", "pip", "install", "--no-deps", str(wheels[0]))
        run(str(python), "-c", "import pycrmkit; print(pycrmkit.__version__)")

    print("PyCRMKit release-check: PASS")


if __name__ == "__main__":
    main()
