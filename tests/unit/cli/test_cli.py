"""Unit tests for PyCRMKit CLI commands and bootstrap."""

from __future__ import annotations

import json
import re
from unittest.mock import patch

from pycrmkit import __version__
from pycrmkit.cli.bootstrap import _detect_prog_name, main
from pycrmkit.cli.exit_codes import ExitCode


def test_exit_codes_constants() -> None:
    assert int(ExitCode.SUCCESS) == 0
    assert int(ExitCode.GENERAL_ERROR) == 1
    assert int(ExitCode.VALIDATION_ERROR) == 2
    assert int(ExitCode.EXECUTION_FAILURE) == 3
    assert int(ExitCode.MISSING_OPTIONAL_DEPENDENCY) == 11


def test_detect_prog_name() -> None:
    assert _detect_prog_name(["pck", "version"]) == "pck"
    assert _detect_prog_name(["pycrm", "version"]) == "pycrm"
    assert _detect_prog_name(["custom_tool"]) == "pck"


def test_cli_help(capsys) -> None:
    code = main(["--help"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    # Rich/Typer may colorize Usage and the executable separately.
    plain_help = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", captured.out + captured.err)
    normalized = " ".join(plain_help.split())
    assert "Usage: pck" in normalized
    for command in ("version", "doctor", "contacts", "seed"):
        assert command in normalized


def test_cli_version_json(capsys) -> None:
    code = main(["version", "--json"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["pycrmkit"]["version"] == __version__
    assert "extras" in data
    assert "cli" in data["extras"]


def test_cli_doctor_json(capsys) -> None:
    code = main(["doctor", "--json"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "healthy"
    assert data["pycrmkit_version"] == __version__
    assert len(data["checks"]) >= 4


def test_cli_tours_single_tour(capsys) -> None:
    code = main(["tours", "-t", "01"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "01_core_crm.py" in captured.out
    assert "PASS" in captured.out


def test_missing_dependency_guard(capsys) -> None:
    with patch("pycrmkit.cli.bootstrap._missing_cli_dependencies", return_value=("fake_pkg",)):
        code = main(["version"], prog_name="pck")
        assert code == int(ExitCode.MISSING_OPTIONAL_DEPENDENCY)
        captured = capsys.readouterr()
        assert "fake_pkg" in captured.err


def test_cli_seed_and_dashboard(tmp_path, monkeypatch, capsys) -> None:
    test_state_file = tmp_path / "cli_test_state.json"
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(test_state_file))

    # 1. Seed demo data
    code = main(["seed"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Demo Enterprise Scenario Loaded" in captured.out
    assert test_state_file.exists()

    # 2. Render executive dashboard
    code = main(["dashboard"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "PyCRMKit Executive Command Center" in captured.out
    assert "Active Pipeline" in captured.out
    assert "Commercial Sales Funnel" in captured.out
    assert "Active Multi-Channel Campaigns" in captured.out


def test_cli_contacts_crud(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("COLUMNS", "160")
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(tmp_path / "contacts_test.json"))

    # Create contact
    code = main(
        ["contacts", "create", "Grace", "Hopper", "--email", "grace@navy.mil"], prog_name="pck"
    )
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Contact Created Successfully" in captured.out
    assert "Grace Hopper" in captured.out

    # List contacts
    code = main(["contacts", "list"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Grace Hopper" in captured.out
    assert "grace@navy" in captured.out


def test_cli_orgs_crud(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("COLUMNS", "160")
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(tmp_path / "orgs_test.json"))

    # Create org
    code = main(["orgs", "create", "DARPA Research Lab", "--trade-name", "DARPA"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Organization Created Successfully" in captured.out

    # List orgs
    code = main(["orgs", "list"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "DARPA Research Lab" in captured.out


def test_cli_sales_and_opportunities(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("COLUMNS", "160")
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(tmp_path / "sales_test.json"))
    main(["seed"], prog_name="pck")
    capsys.readouterr()

    # List pipelines
    code = main(["sales", "pipelines"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "b2b-enterprise" in captured.out

    # List opps
    code = main(["sales", "opps"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Quantique" in captured.out or "Calculat" in captured.out


def test_cli_campaigns_and_tasks(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("COLUMNS", "160")
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(tmp_path / "camps_tasks_test.json"))
    main(["seed"], prog_name="pck")
    capsys.readouterr()

    # List campaigns
    code = main(["campaigns", "list"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Tech" in captured.out and "Summit" in captured.out

    # View audience
    code = main(["campaigns", "audience", "summit-europe-2026"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Audience Members" in captured.out
    assert "Contact" in captured.out

    # List tasks
    code = main(["tasks", "list"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Action Items & Tasks" in captured.out

    # 360° Show Organization
    code = main(["orgs", "show", "curie"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "CURIE TECHNOLOGIES" in captured.out
    assert "Directrice Scientifique" in captured.out
    assert "TOTAL PIPELINE" in captured.out

    # 360° Show Contact
    code = main(["contacts", "show", "marie"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "Marie Curie" in captured.out
    assert "Curie Tech" in captured.out
    assert "Tech Summit" in captured.out

    # Contact Disambiguation
    code = main(["contacts", "show", "curie"], prog_name="pck")
    assert code == int(ExitCode.GENERAL_ERROR)
    captured = capsys.readouterr()
    assert "Plusieurs contacts correspondent" in captured.out

    # Reset store
    code = main(["reset", "--force"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    captured = capsys.readouterr()
    assert "CRM State Successfully Cleared" in captured.out


def test_cli_rejects_invalid_explicit_yaml(tmp_path, monkeypatch, capsys) -> None:
    config = tmp_path / "invalid.yml"
    config.write_text("database: [unclosed\n", encoding="utf-8")
    monkeypatch.setenv("PYCRMKIT_CONFIG", str(config))
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    assert main(["version", "--json"], prog_name="pck") == int(ExitCode.VALIDATION_ERROR)
    assert "Configuration error:" in capsys.readouterr().err


def test_seed_refuses_implicit_persistent_database(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PYCRMKIT_DATABASE_URL", "postgresql+psycopg://localhost/not_a_test_db")
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    assert main(["seed"], prog_name="pck") == int(ExitCode.VALIDATION_ERROR)
    assert "database is configured" in capsys.readouterr().out
    assert main(["seed", "--database"], prog_name="pck") == int(ExitCode.VALIDATION_ERROR)
    assert "require --database --yes" in capsys.readouterr().out
    assert not (tmp_path / "cli_state.json").exists()


def test_dashboard_demo_never_contacts_configured_database(tmp_path, monkeypatch, capsys) -> None:
    state_file = tmp_path / "should_not_exist.json"
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(state_file))
    monkeypatch.setenv("PYCRMKIT_DATABASE_URL", "postgresql+psycopg://localhost/unreachable_db")
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    code = main(["dashboard", "--demo"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    out = capsys.readouterr().out
    # Rich can wrap the mode label at different terminal widths.
    assert "Ephemeral" in out
    assert not state_file.exists()


def test_seed_rejects_production_profile_without_database_access(monkeypatch, capsys) -> None:
    monkeypatch.setenv("PYCRMKIT_ENV", "production")
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    monkeypatch.setenv("PYCRMKIT_DATABASE_URL", "postgresql+psycopg://localhost/production")
    assert main(["seed", "--database", "--yes"], prog_name="pck") == int(
        ExitCode.VALIDATION_ERROR
    )
    assert "prohibited in production" in capsys.readouterr().out


def test_doctor_rejects_unreachable_explicit_backend_without_secret_disclosure(
    monkeypatch, capsys
) -> None:
    secret = "test-password"
    url = f"postgresql+psycopg://testuser:{secret}@127.0.0.1:1/missing"
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    monkeypatch.setenv("PYCRMKIT_DATABASE_URL", url)
    monkeypatch.delenv("PYCRMKIT_CONFIG", raising=False)
    code = main(["doctor", "--json"], prog_name="pck")
    output = capsys.readouterr()
    assert code == int(ExitCode.GENERAL_ERROR)
    data = json.loads(output.out)
    assert data["status"] == "unhealthy"
    assert any(
        check["name"] == "Database Live Ping" and check["status"] == "FAIL"
        for check in data["checks"]
    )
    assert secret not in output.out + output.err
    assert "testuser" not in output.out + output.err


def test_cli_never_prints_credentials_on_database_connection_failure(
    monkeypatch, capsys
) -> None:
    secret = "demo-password"
    monkeypatch.setenv(
        "PYCRMKIT_DATABASE_URL",
        f"postgresql+psycopg://ci_operator:{secret}@127.0.0.1:1/unreachable",
    )
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    monkeypatch.delenv("PYCRMKIT_CONFIG", raising=False)
    assert main(["contacts", "list"], prog_name="pck") != int(ExitCode.SUCCESS)
    out = capsys.readouterr()
    assert secret not in out.out + out.err
    assert "ci_operator" not in out.out + out.err


def test_production_profile_refuses_local_seed_and_reset(
    tmp_path, monkeypatch, capsys
) -> None:
    from pycrmkit.cli.state import MemoryStore, save_store

    target = tmp_path / "existing.json"
    save_store(MemoryStore(), target)
    original = target.read_bytes()
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(target))
    monkeypatch.setenv("PYCRMKIT_ENV", "production")
    monkeypatch.setenv("PYCRMKIT_TEST_ENABLE_ENV", "1")
    monkeypatch.delenv("PYCRMKIT_CONFIG", raising=False)

    assert main(["seed", "--local"], prog_name="pck") == int(ExitCode.VALIDATION_ERROR)
    assert main(["reset", "--force"], prog_name="pck") == int(ExitCode.VALIDATION_ERROR)
    assert target.read_bytes() == original
    assert "prohibited in production" in capsys.readouterr().out
