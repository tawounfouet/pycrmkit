"""Dependency-light bootstrap for the PyCRMKit CLI."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path

from pycrmkit.cli.exit_codes import ExitCode

CLI_DEPENDENCIES = ("typer", "rich")
MISSING_DEPENDENCY_EXIT_CODE = int(ExitCode.MISSING_OPTIONAL_DEPENDENCY)


def _missing_cli_dependencies() -> tuple[str, ...]:
    """Identify any missing dependencies required to run the CLI."""
    return tuple(dep for dep in CLI_DEPENDENCIES if importlib.util.find_spec(dep) is None)


def _bootstrap_environment() -> None:
    """Load local environment configuration from .env and declarative pycrm.yml."""
    import os

    if "PYTEST_CURRENT_TEST" in os.environ and not os.getenv("PYCRMKIT_TEST_ENABLE_ENV"):
        return

    from pycrmkit.cli.config import load_local_dotenv, load_yaml_config

    load_local_dotenv()
    cfg = load_yaml_config()
    if cfg.source == "file":
        if cfg.database.url and "DATABASE_URL" not in os.environ and "PYCRMKIT_DATABASE_URL" not in os.environ:
            os.environ["DATABASE_URL"] = cfg.database.url
        if cfg.runtime.actor_id and "CRM_ACTOR_ID" not in os.environ:
            os.environ["CRM_ACTOR_ID"] = cfg.runtime.actor_id


def _detect_prog_name(argv: Sequence[str] | None = None) -> str:
    """Determine the CLI program name from invocation or fallback to 'pck'."""
    if argv and argv[0] in ("pck", "pycrm", "pycrmkit"):
        return argv[0]
    raw = sys.argv[0] if sys.argv else ""
    basename = Path(raw).name
    if basename in ("pck", "pycrm", "pycrmkit"):
        return basename
    return "pck"


def main(argv: Sequence[str] | None = None, prog_name: str | None = None) -> int:
    """Run PyCRMKit CLI with dependency guards and graceful signal handling."""
    missing = _missing_cli_dependencies()
    if missing:
        deps = ", ".join(missing)
        print(
            f"PyCRMKit CLI dependencies missing: {deps}.\n"
            'Install CLI dependencies via: pip install "pycrmkit[cli]" '
            "or pip install typer rich",
            file=sys.stderr,
        )
        return MISSING_DEPENDENCY_EXIT_CODE

    # Load local environment and declarative YAML configuration
    _bootstrap_environment()

    # Dynamic import of heavy Typer application
    from pycrmkit.cli.app import app

    resolved_prog = prog_name or _detect_prog_name(argv)
    args = list(argv) if argv is not None else None

    try:
        app(args=args, prog_name=resolved_prog, standalone_mode=True)
        return int(ExitCode.SUCCESS)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except KeyboardInterrupt:
        return int(ExitCode.INTERRUPTED)
    except BrokenPipeError:
        return int(ExitCode.BROKEN_PIPE)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)


if __name__ == "__main__":
    sys.exit(main())
