"""Security and failure-contract tests for CLI local JSON state (AUD-FIX-02)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pycrmkit.cli.state import (
    CLIStateError,
    _exclusive_state_lock,
    build_crm_from_store,
    load_store,
    save_store,
    seed_demo_data,
)
from pycrmkit.cli.state_codec import dump_state, load_state
from pycrmkit.storage.memory._state import MemoryStore


def test_empty_store_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    save_store(MemoryStore(), target)
    assert target.read_bytes().startswith(b'{"schema_version":1,')
    assert load_store(target)._state.contacts == {}


def test_full_seed_roundtrip_across_process_equivalent(tmp_path: Path) -> None:
    target = tmp_path / "seed.json"
    store = MemoryStore()
    counts = seed_demo_data(build_crm_from_store(store))
    assert counts["contacts"] > 0
    save_store(store, target)

    restored = load_store(target)
    crm = build_crm_from_store(restored)
    assert crm.contacts.search().total == counts["contacts"]
    assert crm.organizations.search().total == counts["organizations"]


@pytest.mark.parametrize("payload", [b"", b"not-json", b"\x80\x04\x95\x00", b"[]"])
def test_malformed_or_pickle_data_is_rejected(tmp_path: Path, payload: bytes) -> None:
    target = tmp_path / "state.json"
    target.write_bytes(payload)
    with pytest.raises(CLIStateError):
        load_store(target)


def test_unknown_version_and_type_tags_are_rejected() -> None:
    raw = dump_state(MemoryStore()._state)
    payload = json.loads(raw)
    payload["schema_version"] = 42
    with pytest.raises(CLIStateError, match="schema version"):
        load_state(json.dumps(payload).encode())

    payload["schema_version"] = 1
    payload["state"]["type"] = "os.system"
    with pytest.raises(CLIStateError, match="Unregistered"):
        load_state(json.dumps(payload).encode())


def test_legacy_pickle_file_is_never_opened(tmp_path: Path) -> None:
    target = tmp_path / "crm_state.pickle"
    target.write_bytes(b"\x80\x04")
    with patch("builtins.open", side_effect=AssertionError("legacy file opened")):
        with pytest.raises(CLIStateError, match="Legacy pickle"):
            load_store(target)


def test_writer_lock_rejects_concurrent_writer(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    with _exclusive_state_lock(target):
        with pytest.raises(CLIStateError, match="locked"):
            save_store(MemoryStore(), target)


def test_failed_atomic_replace_preserves_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    store = MemoryStore()
    save_store(store, target)
    original = target.read_bytes()

    with patch("pycrmkit.cli.state.os.replace", side_effect=OSError("injected failure")):
        with pytest.raises(CLIStateError, match="atomically"):
            save_store(store, target)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob(".pycrmkit-state-*.tmp"))


def test_permissions_are_private_on_posix(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    save_store(MemoryStore(), target)
    assert target.stat().st_mode & 0o077 == 0


def test_reset_never_races_a_concurrent_state_writer(tmp_path: Path, monkeypatch) -> None:
    from pycrmkit.cli.commands.seed import reset_command

    target = tmp_path / "state.json"
    save_store(MemoryStore(), target)
    monkeypatch.setenv("PYCRMKIT_CLI_STATE_FILE", str(target))
    original = target.read_bytes()
    with _exclusive_state_lock(target):
        with pytest.raises(CLIStateError, match="locked"):
            reset_command(force=True)
    assert target.read_bytes() == original

    reset_command(force=True)
    assert not target.exists()


def test_json_duplicate_keys_rejected_even_in_nested_models() -> None:
    raw = dump_state(MemoryStore()._state)
    # Duplicated top-level schema names are not silently resolved by json.loads.
    injected = raw.replace(b'"schema_version":1,', b'"schema_version":1,"schema_version":1,')
    with pytest.raises(CLIStateError, match="Duplicate key"):
        load_state(injected)

    nested = raw.replace(b'"kind":"model",', b'"kind":"model","kind":"model",', 1)
    with pytest.raises(CLIStateError, match="Duplicate key"):
        load_state(nested)


@pytest.mark.parametrize("bad_value", [b'NaN', b'Infinity', b'-Infinity'])
def test_json_rejects_nonstandard_float_constants(bad_value: bytes) -> None:
    raw = dump_state(MemoryStore()._state)
    injected = raw.replace(b'"schema_version":1', b'"schema_version":' + bad_value, 1)
    with pytest.raises(CLIStateError):
        load_state(injected)


def test_state_rejects_partial_or_wrongly_typed_collections() -> None:
    obj = json.loads(dump_state(MemoryStore()._state))
    del obj["state"]["fields"]["contacts"]
    with pytest.raises(CLIStateError, match="Missing or unknown"):
        load_state(json.dumps(obj).encode())

    obj = json.loads(dump_state(MemoryStore()._state))
    obj["state"]["fields"]["contacts"] = []
    with pytest.raises(CLIStateError, match="Invalid MemoryStore collection"):
        load_state(json.dumps(obj).encode())


def test_malformed_state_does_not_overwrite_prior_valid_bytes(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    save_store(MemoryStore(), target)
    obj = json.loads(target.read_bytes())
    del obj["state"]["fields"]["contacts"]
    invalid = json.dumps(obj).encode()
    target.write_bytes(invalid)
    with pytest.raises(CLIStateError):
        load_store(target)
    assert target.read_bytes() == invalid


def test_state_rejects_forged_repository_id_and_aggregate_types() -> None:
    obj = json.loads(dump_state(MemoryStore()._state))
    # A primitive string must never become a ContactId key.
    obj["state"]["fields"]["contacts"]["items"] = [["not-a-contact-id", "not-a-contact"]]
    with pytest.raises(CLIStateError, match="key/value contract: contacts"):
        load_state(json.dumps(obj).encode())

    # Even apparently harmless string-keyed pipelines need Pipeline values.
    obj = json.loads(dump_state(MemoryStore()._state))
    obj["state"]["fields"]["pipelines"]["items"] = [["known-pipeline", 123]]
    with pytest.raises(CLIStateError, match="key/value contract: pipelines"):
        load_state(json.dumps(obj).encode())
