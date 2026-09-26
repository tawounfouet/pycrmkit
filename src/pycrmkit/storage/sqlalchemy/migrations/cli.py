"""Installed-package command line for PyCRMKit Alembic migrations."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

SCRIPT_LOCATION = "pycrmkit.storage.sqlalchemy:migrations"
DATABASE_ENV = "PYCRMKIT_DATABASE_URL"


def migration_config(database_url: str | None = None):
    """Build an Alembic Config using the packaged migration environment."""

    try:
        from alembic.config import Config
    except ModuleNotFoundError as error:
        raise RuntimeError(
            'Alembic is not installed. Install PyCRMKit with "pycrmkit[migrations]".'
        ) from error

    url = database_url or os.environ.get(DATABASE_ENV)
    if not url:
        raise ValueError(
            f"Set {DATABASE_ENV} or pass --database-url before running migrations"
        )

    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    config.set_main_option("sqlalchemy.url", url)
    return config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pycrmkit-migrate",
        description="Run PyCRMKit persistence migrations.",
    )
    parser.add_argument(
        "--database-url",
        help=f"SQLAlchemy database URL; defaults to {DATABASE_ENV}.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    upgrade = subparsers.add_parser("upgrade")
    upgrade.add_argument("revision", nargs="?", default="head")

    downgrade = subparsers.add_parser("downgrade")
    downgrade.add_argument("revision")

    subparsers.add_parser("current")
    subparsers.add_parser("check")

    stamp = subparsers.add_parser("stamp")
    stamp.add_argument("revision")

    history = subparsers.add_parser("history")
    history.add_argument("range", nargs="?")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the packaged Alembic command surface."""

    parser = _parser()
    args = parser.parse_args(argv)

    try:
        from alembic import command as alembic_command

        config = migration_config(args.database_url)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))

    if args.command == "upgrade":
        alembic_command.upgrade(config, args.revision)
    elif args.command == "downgrade":
        alembic_command.downgrade(config, args.revision)
    elif args.command == "current":
        alembic_command.current(config)
    elif args.command == "check":
        alembic_command.check(config)
    elif args.command == "stamp":
        alembic_command.stamp(config, args.revision)
    elif args.command == "history":
        alembic_command.history(config, rev_range=args.range)
    else:  # pragma: no cover - argparse enforces the command choices.
        parser.error(f"Unsupported migration command: {args.command}")

    return 0


__all__ = ["DATABASE_ENV", "SCRIPT_LOCATION", "main", "migration_config"]
