"""AUD-FIX-07: CLI actor provenance and effective mock transport."""

from __future__ import annotations

import json

from pycrmkit.cli.bootstrap import main
from pycrmkit.cli.exit_codes import ExitCode
from pycrmkit.cli.state import get_crm_context


def test_actor_from_environment_is_used_for_audit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CRM_ACTOR_ID", "track-s-claimed-actor")
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(tmp_path / "crm_state.json"))
    with get_crm_context(save=True, force_local=True) as crm:
        assert crm.context.actor_id == "track-s-claimed-actor"
        contact = crm.contacts.create(first_name="Ada", last_name="Example")
        audit = crm.audit.for_entity("contact", contact.id)
        assert any(x.actor_id == "track-s-claimed-actor" for x in audit.items)


def test_explicit_actor_overrides_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CRM_ACTOR_ID", "configured-actor")
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(tmp_path / "crm_state.json"))
    with get_crm_context(force_local=True, actor_id="explicit-actor") as crm:
        assert crm.context.actor_id == "explicit-actor"


def test_doctor_reports_mock_as_non_delivery(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PYCRMKIT_DATABASE_URL", raising=False)
    code = main(["doctor", "--json"], prog_name="pck")
    assert code == int(ExitCode.SUCCESS)
    report = json.loads(capsys.readouterr().out)
    provider = next(x for x in report["checks"] if x["name"] == "Effective CLI Email Provider")
    assert "mock-cli-mailer" in provider["details"]
    assert "no external delivery" in provider["details"]
