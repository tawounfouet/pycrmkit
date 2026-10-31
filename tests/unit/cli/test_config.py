"""Unit tests for declarative configuration loader and dotenv discovery in PyCRMKit CLI."""

from __future__ import annotations

import os
from pathlib import Path

from pycrmkit.cli.config import (
    CLIConfig,
    _parse_simple_dotenv_line,
    _substitute_env_vars,
    find_config_file,
    find_dotenv_file,
    load_local_dotenv,
    load_yaml_config,
    resolve_actor_id,
    resolve_database_url,
)


def test_simple_dotenv_parser() -> None:
    assert _parse_simple_dotenv_line("# This is a comment") is None
    assert _parse_simple_dotenv_line("   ") is None
    assert _parse_simple_dotenv_line("INVALID_LINE_NO_EQUALS") is None
    assert _parse_simple_dotenv_line("KEY=value") == ("KEY", "value")
    assert _parse_simple_dotenv_line('export DATABASE_URL="postgresql://localhost/crm"') == (
        "DATABASE_URL",
        "postgresql://localhost/crm",
    )
    assert _parse_simple_dotenv_line("ACTOR='thomas@agency.fr'") == (
        "ACTOR",
        "thomas@agency.fr",
    )


def test_env_var_substitution(monkeypatch) -> None:
    monkeypatch.setenv("TEST_HOST", "db.internal")
    monkeypatch.delenv("NON_EXISTENT_VAR", raising=False)

    template = "postgresql://${TEST_HOST}:${NON_EXISTENT_VAR:-5432}/crm"
    result = _substitute_env_vars(template)
    assert result == "postgresql://db.internal:5432/crm"


def test_find_and_load_dotenv(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CRM_TEST_VAR=discovered_value\nCRM_OTHER=123\n")

    monkeypatch.delenv("CRM_TEST_VAR", raising=False)
    monkeypatch.delenv("CRM_OTHER", raising=False)

    found = find_dotenv_file(cwd=tmp_path)
    assert found == env_file.resolve()

    target, count = load_local_dotenv(dotenv_path=env_file)
    assert target == env_file
    assert count == 2
    assert os.getenv("CRM_TEST_VAR") == "discovered_value"
    assert os.getenv("CRM_OTHER") == "123"


def test_find_and_load_yaml_config(tmp_path, monkeypatch) -> None:
    yaml_file = tmp_path / "pycrm.yml"
    yaml_file.write_text(
        """version: "1.0"
runtime:
  actor_id: "agent-007@test.agency"
  environment: "staging"
database:
  backend: "postgresql"
  url: "postgresql+psycopg://user:secret@localhost:5432/crm_test"
  pool_size: 15
integrations:
  email:
    provider: "resend"
    api_key_env: "RESEND_KEY"
"""
    )

    found = find_config_file(cwd=tmp_path)
    assert found == yaml_file.resolve()

    cfg: CLIConfig = load_yaml_config(config_path=yaml_file)
    assert cfg.source == "file"
    assert cfg.runtime.actor_id == "agent-007@test.agency"
    assert cfg.runtime.environment == "staging"
    assert cfg.database.backend == "postgresql"
    assert cfg.database.url == "postgresql+psycopg://user:secret@localhost:5432/crm_test"
    assert cfg.database.pool_size == 15
    assert cfg.integrations.email.provider == "resend"


def test_resolve_hierarchy(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    yaml_file = tmp_path / "pycrm.yml"
    yaml_file.write_text(
        """database:
  url: "postgresql://from_yaml/db"
runtime:
  actor_id: "from_yaml_actor"
"""
    )
    monkeypatch.chdir(tmp_path)

    # 1. Resolves from YAML file
    url, source = resolve_database_url()
    assert url == "postgresql://from_yaml/db"
    assert "config:" in source

    actor, actor_src = resolve_actor_id()
    assert actor == "from_yaml_actor"
    assert "config:" in actor_src

    # 2. Environment variable overrides YAML
    monkeypatch.setenv("DATABASE_URL", "postgresql://from_env/db")
    monkeypatch.setenv("CRM_ACTOR_ID", "from_env_actor")

    url, source = resolve_database_url()
    assert url == "postgresql://from_env/db"
    assert source == "env:DATABASE_URL"

    actor, actor_src = resolve_actor_id()
    assert actor == "from_env_actor"
    assert actor_src == "env:CRM_ACTOR_ID"
