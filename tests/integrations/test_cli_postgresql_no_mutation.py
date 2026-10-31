"""Real PostgreSQL no-mutation qualification for CLI demonstration commands.

This is a dedicated isolated CI database; never point it at production.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from pycrmkit.cli.bootstrap import main
from pycrmkit.cli.exit_codes import ExitCode

pytestmark = pytest.mark.postgresql


@pytest.fixture
def isolated_database_url() -> str:
    url = os.getenv("PYCRMKIT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PYCRMKIT_TEST_POSTGRES_URL is required for live CLI security qualification")
    parsed = make_url(url)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.host not in {"localhost", "127.0.0.1"}
        or parsed.database != "pycrmkit_s0_guard"
    ):
        pytest.fail("Live CLI security tests require the dedicated loopback guard database")
    return url


def test_refused_seed_and_ephemeral_dashboard_do_not_change_database(
    isolated_database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine = create_engine(isolated_database_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS cli_s0_guard (id integer PRIMARY KEY, marker text NOT NULL)"))
        conn.execute(text("DELETE FROM cli_s0_guard"))
        conn.execute(text("INSERT INTO cli_s0_guard (id, marker) VALUES (1, 'untouched')"))

    with engine.connect() as conn:
        tables_before = set(inspect(conn).get_table_names())

    # Even accidental attempts to initialize a database engine are forbidden
    # for implicitly refused seeds and the explicitly ephemeral demo view.
    database_access_attempts: list[str] = []

    def forbid_engine(*args: object, **kwargs: object) -> object:
        database_access_attempts.append("unexpected SQLAlchemy engine creation")
        raise AssertionError("Demonstration commands must not access PostgreSQL")

    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    monkeypatch.setenv("PYCRMKIT_DATABASE_URL", isolated_database_url)
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(tmp_path / "demo-state.json"))
    monkeypatch.delenv("PYCRMKIT_CONFIG", raising=False)
    monkeypatch.setenv("PYCRMKIT_ENV", "development")

    with monkeypatch.context() as blocked:
        blocked.setattr("sqlalchemy.create_engine", forbid_engine)
        assert main(["seed"], prog_name="pck") == int(ExitCode.VALIDATION_ERROR)
        assert main(["seed", "--database"], prog_name="pck") == int(ExitCode.VALIDATION_ERROR)
        assert main(["dashboard", "--demo"], prog_name="pck") == int(ExitCode.SUCCESS)
    capsys.readouterr()

    assert database_access_attempts == []
    with engine.connect() as conn:
        assert set(inspect(conn).get_table_names()) == tables_before
        assert conn.execute(text("SELECT id, marker FROM cli_s0_guard")).all() == [
            (1, "untouched")
        ]
    assert not (tmp_path / "demo-state.json").exists()
    engine.dispose()


def test_production_demo_write_rejected_before_persistent_access(
    isolated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    monkeypatch.setenv("PYCRMKIT_DATABASE_URL", isolated_database_url)
    monkeypatch.setenv("PYCRMKIT_ENV", "production")
    monkeypatch.delenv("PYCRMKIT_CONFIG", raising=False)
    database_access_attempts: list[str] = []

    def forbid_engine(*args: object, **kwargs: object) -> object:
        database_access_attempts.append("unexpected SQLAlchemy engine creation")
        raise AssertionError("Production demo commands must not access PostgreSQL")

    with monkeypatch.context() as blocked:
        blocked.setattr("sqlalchemy.create_engine", forbid_engine)
        assert main(["seed", "--database", "--yes"], prog_name="pck") == int(
            ExitCode.VALIDATION_ERROR
        )
        assert main(["reset", "--database", "--yes"], prog_name="pck") == int(
            ExitCode.VALIDATION_ERROR
        )

    assert database_access_attempts == []
