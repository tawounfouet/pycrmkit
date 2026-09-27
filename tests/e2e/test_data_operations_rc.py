"""Release-candidate E2E for the complete V0.9 Data Operations journey."""

from __future__ import annotations

from examples.data_operations.scenario import run_scenario


def test_data_operations_release_candidate_end_to_end() -> None:
    summary = run_scenario()

    assert summary["version"] == "0.9.0"
    assert summary["import"] == {
        "rows_read": 4,
        "rows_created": 3,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 0,
        "validation_errors": 1,
    }
    assert summary["review"] == {
        "decision": "duplicate",
        "score": 100,
        "matched_signals": ["email", "full_name", "phone"],
    }

    merge = summary["merge"]
    assert isinstance(merge, dict)
    assert merge["audit_action"] == "contact.merged"
    assert merge["duplicate_archived"] is True
    assert merge["external_identity_owner"] == "primary"

    assert summary["export"] == {
        "active_contacts": 2,
        "csv_rows": 2,
        "json_rows": 2,
        "jsonl_rows": 2,
        "display_names": ["Ada Lovelace", "Grace Hopper"],
    }
