"""RC-02 cross-layer E2E qualification for the V1 production candidate."""

from __future__ import annotations

from examples.production_qualification.scenario import run_scenario


def test_v1_cross_layer_production_qualification() -> None:
    summary = run_scenario()

    assert summary["version"] == "1.2.0a2"
    assert summary["qualification"] == "1.0.0-rc02-cross-layer-e2e"

    headless = summary["headless_customer_journey"]
    assert isinstance(headless, dict)
    assert headless["opportunity_status"] == "won"
    assert headless["opportunity_stage"] == "won"
    assert headless["webhook_state"] == "succeeded"
    assert headless["webhook_attempts"] == 1
    assert headless["email_status"] == "delivered"
    assert headless["audit_entries"] >= 17
    assert {
        "activity.created",
        "task.created",
        "task.started",
        "task.completed",
        "email.queued",
        "email.sent",
        "email.delivered",
    } <= set(headless["timeline_event_types"])

    data_operations = summary["data_operations"]
    assert isinstance(data_operations, dict)
    assert data_operations["import"] == {
        "rows_read": 4,
        "rows_created": 3,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 0,
        "validation_errors": 1,
    }
    assert data_operations["review"] == {
        "decision": "duplicate",
        "score": 100,
        "matched_signals": ["email", "full_name", "phone"],
    }
    assert data_operations["export"] == {
        "active_contacts": 2,
        "csv_rows": 2,
        "json_rows": 2,
        "jsonl_rows": 2,
        "display_names": ["Ada Lovelace", "Grace Hopper"],
    }
    merge = data_operations["merge"]
    assert isinstance(merge, dict)
    assert merge["audit_action"] == "contact.merged"
    assert merge["duplicate_archived"] is True
    assert merge["external_identity_owner"] == "primary"
