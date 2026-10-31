"""Restricted, versioned JSON codec for local PyCRMKit CLI MemoryStore state.

No Python object deserialization, import-by-name, eval, or pickle occurs on the
untrusted-file read path. Allowed model types are discovered *only* from the
installed package's typed _MemoryState schema and its nested dataclasses.
"""

from __future__ import annotations

import base64
import dataclasses
import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from math import isfinite
from types import MappingProxyType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints
from uuid import UUID

from pycrmkit.storage.memory._state import _MemoryState

SCHEMA_VERSION = 1
MAX_STATE_BYTES = 16 * 1024 * 1024
MAX_DEPTH = 80


class CLIStateError(ValueError):
    """Local CLI state cannot be safely loaded or saved."""


def _model_key(cls: type[Any]) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


@lru_cache(maxsize=1)
def _allowed_models() -> dict[str, type[Any]]:
    """Construct an allowlist from the trusted package schema, never disk input."""
    allowed: dict[str, type[Any]] = {}
    seen: set[type[Any]] = set()

    def walk(annotation: Any) -> None:
        if isinstance(annotation, type):
            cls = annotation
            if cls in seen:
                return
            seen.add(cls)
            if not cls.__module__.startswith("pycrmkit."):
                return
            if not (dataclasses.is_dataclass(cls) or issubclass(cls, Enum)):
                return
            allowed[_model_key(cls)] = cls
            if dataclasses.is_dataclass(cls):
                for value in get_type_hints(cls).values():
                    walk(value)
        for arg in get_args(annotation):
            walk(arg)

    walk(_MemoryState)

    # Generic entity bases can erase concrete typed-ID annotations at runtime.
    # These subclasses are defined by the installed PyCRMKit package, never by
    # strings from disk, and must be registered before decoding stored tags.
    from pycrmkit.core.ids import UUIDId

    def register_ids(base: type[UUIDId]) -> None:
        for subclass in base.__subclasses__():
            if subclass.__module__.startswith("pycrmkit."):
                allowed[_model_key(subclass)] = subclass
                register_ids(subclass)

    register_ids(UUIDId)
    return allowed


def _encode(value: object, depth: int = 0) -> object:
    if depth > MAX_DEPTH:
        raise CLIStateError("CLI state exceeds maximum nesting depth")
    if isinstance(value, Enum):
        cls = type(value)
        name = _model_key(cls)
        if name not in _allowed_models():
            raise CLIStateError("Unregistered enum in CLI state")
        return {"kind": "enum", "type": name, "value": value.value}
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not isfinite(value):
            raise CLIStateError("Non-finite float cannot be persisted")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CLIStateError("Non-finite Decimal cannot be persisted")
        return {"kind": "decimal", "value": str(value)}
    if isinstance(value, UUID):
        return {"kind": "uuid", "value": str(value)}
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CLIStateError("Naive datetime cannot be persisted")
        return {"kind": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"kind": "date", "value": value.isoformat()}
    if isinstance(value, bytes):
        return {"kind": "bytes", "value": base64.b64encode(value).decode("ascii")}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        model_cls = type(value)
        name = _model_key(model_cls)
        if name not in _allowed_models():
            raise CLIStateError(f"Unregistered domain object: {name}")
        return {
            "kind": "model",
            "type": name,
            "fields": {
                field.name: _encode(getattr(value, field.name), depth + 1)
                for field in dataclasses.fields(value)
                if field.init
            },
        }
    if isinstance(value, Mapping):
        return {
            "kind": "frozen_map" if isinstance(value, MappingProxyType) else "map",
            "items": [
                [_encode(k, depth + 1), _encode(v, depth + 1)]
                for k, v in value.items()
            ],
        }
    if isinstance(value, tuple):
        return {"kind": "tuple", "items": [_encode(v, depth + 1) for v in value]}
    if isinstance(value, (set, frozenset)):
        return {
            "kind": "frozenset" if isinstance(value, frozenset) else "set",
            "items": [_encode(v, depth + 1) for v in value],
        }
    if isinstance(value, list):
        return [_encode(v, depth + 1) for v in value]
    raise CLIStateError(f"Unsupported CLI state value: {type(value).__name__}")


def _expect_keys(value: dict[str, object], required: set[str]) -> None:
    if set(value) != required:
        raise CLIStateError("Malformed CLI state type envelope")


def _decode(value: object, depth: int = 0) -> object:
    if depth > MAX_DEPTH:
        raise CLIStateError("CLI state exceeds maximum nesting depth")
    if value is None or type(value) in (str, bool, int, float):
        if type(value) is float and not isfinite(value):
            raise CLIStateError("Non-finite float in CLI state")
        return value
    if isinstance(value, list):
        return [_decode(v, depth + 1) for v in value]
    if not isinstance(value, dict):
        raise CLIStateError("Invalid CLI state data type")
    kind = value.get("kind")
    if kind in ("decimal", "uuid", "datetime", "date", "bytes"):
        _expect_keys(value, {"kind", "value"})
        raw = value["value"]
        if not isinstance(raw, str):
            raise CLIStateError("Invalid scalar encoding")
        try:
            if kind == "decimal":
                number = Decimal(raw)
                if number.is_finite():
                    return number
            if kind == "uuid":
                return UUID(raw)
            if kind == "datetime":
                parsed = datetime.fromisoformat(raw)
                if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                    return parsed
            if kind == "date":
                return date.fromisoformat(raw)
            if kind == "bytes":
                return base64.b64decode(raw, validate=True)
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise CLIStateError("Invalid encoded scalar") from exc
        raise CLIStateError("Invalid non-finite or timezone-naive scalar")
    if kind == "enum":
        _expect_keys(value, {"kind", "type", "value"})
        name = value["type"]
        cls = _allowed_models().get(name) if isinstance(name, str) else None
        if cls is None or not issubclass(cls, Enum):
            raise CLIStateError("Unregistered enum tag")
        raw = value["value"]
        if type(raw) not in (str, int):
            raise CLIStateError("Invalid enum value")
        try:
            return cls(raw)
        except ValueError as exc:
            raise CLIStateError("Unknown enum member") from exc
    if kind == "model":
        _expect_keys(value, {"kind", "type", "fields"})
        name = value["type"]
        cls = _allowed_models().get(name) if isinstance(name, str) else None
        if cls is None or not dataclasses.is_dataclass(cls):
            raise CLIStateError("Unregistered domain class tag")
        data = value["fields"]
        if not isinstance(data, dict) or not all(isinstance(k, str) for k in data):
            raise CLIStateError("Invalid domain object fields")
        allowed_fields = {f.name for f in dataclasses.fields(cls) if f.init}
        if set(data) != allowed_fields:
            raise CLIStateError("Missing or unknown domain object field")
        kwargs = {k: _decode(v, depth + 1) for k, v in data.items()}
        try:
            return cls(**kwargs)
        except Exception as exc:  # noqa: BLE001 - untrusted model constructor boundary
            raise CLIStateError("Invalid domain object in local state") from exc
    if kind in ("map", "frozen_map", "tuple", "set", "frozenset"):
        _expect_keys(value, {"kind", "items"})
        items = value["items"]
        if not isinstance(items, list):
            raise CLIStateError("Invalid collection items")
        decoded = [_decode(v, depth + 1) for v in items]
        if kind == "tuple":
            return tuple(decoded)
        if kind in ("set", "frozenset"):
            try:
                return frozenset(decoded) if kind == "frozenset" else set(decoded)
            except TypeError as exc:
                raise CLIStateError("Unhashable element in state set") from exc
        mapping: dict[object, object] = {}
        for pair in decoded:
            if not isinstance(pair, list) or len(pair) != 2:
                raise CLIStateError("Invalid mapping pair")
            try:
                if pair[0] in mapping:
                    raise CLIStateError("Duplicate mapping key")
                mapping[pair[0]] = pair[1]
            except TypeError as exc:
                raise CLIStateError("Unhashable mapping key") from exc
        return MappingProxyType(mapping) if kind == "frozen_map" else mapping
    raise CLIStateError("Unknown local CLI state type tag")


def dump_state(state: _MemoryState) -> bytes:
    """Encode a full state as bounded UTF-8 JSON with an explicit schema version."""
    if not isinstance(state, _MemoryState):
        raise CLIStateError("Only a MemoryStore snapshot can be saved")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "format": "pycrmkit.cli.memory",
        "state": _encode(state),
    }
    try:
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise CLIStateError("State cannot be encoded") from exc
    encoded = raw.encode("utf-8")
    if len(encoded) > MAX_STATE_BYTES:
        raise CLIStateError("CLI state exceeds configured maximum file size")
    return encoded


def _unique_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON object keys before they can shadow trusted fields."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CLIStateError("Duplicate key in JSON CLI state")
        result[key] = value
    return result


def _reject_invalid_constant(value: str) -> object:
    raise CLIStateError(f"Invalid JSON numeric constant: {value}")


def _matches_state_type(value: object, annotation: Any, depth: int = 0) -> bool:
    """Validate the concrete root repository key/value contracts after decoding."""
    if depth > MAX_DEPTH:
        return False
    if annotation is Any:
        return True
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (UnionType, Union):
        return any(_matches_state_type(value, item, depth + 1) for item in args)
    if origin is list:
        return type(value) is list and all(
            _matches_state_type(item, args[0], depth + 1) for item in value
        )
    if origin is dict:
        return type(value) is dict and all(
            _matches_state_type(k, args[0], depth + 1)
            and _matches_state_type(v, args[1], depth + 1)
            for k, v in value.items()
        )
    if origin is tuple:
        if type(value) is not tuple:
            return False
        if len(args) == 2 and args[1] is Ellipsis:
            return all(_matches_state_type(item, args[0], depth + 1) for item in value)
        return len(value) == len(args) and all(
            _matches_state_type(item, expected, depth + 1)
            for item, expected in zip(value, args, strict=True)
        )
    if isinstance(annotation, type):
        return isinstance(value, annotation)
    return False


def load_state(raw: bytes) -> _MemoryState:
    """Reject invalid schema, corrupt JSON, duplicate keys and forged type tags."""
    if len(raw) > MAX_STATE_BYTES:
        raise CLIStateError("CLI state exceeds configured maximum file size")
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_unique_object_pairs,
            parse_constant=_reject_invalid_constant,
        )
    except CLIStateError:
        # The validation hooks have already identified a specific unsafe input.
        # CLIStateError derives from ValueError, so preserve it explicitly.
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CLIStateError("Malformed JSON CLI state (legacy pickle is not supported)") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "format", "state"}:
        raise CLIStateError("Invalid local CLI state envelope")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise CLIStateError("Unsupported local CLI state schema version")
    if payload["format"] != "pycrmkit.cli.memory":
        raise CLIStateError("Unknown local CLI state format")
    try:
        decoded = _decode(payload["state"])
    except (RecursionError, OverflowError) as exc:
        raise CLIStateError("Malformed or deeply nested local state") from exc
    if type(decoded) is not _MemoryState:
        raise CLIStateError("CLI state root must be a MemoryStore snapshot")
    # All root collections are real dicts in this schema. Bad JSON must never
    # silently become an empty, partially missing or incorrectly typed store.
    annotations = get_type_hints(_MemoryState)
    for field in dataclasses.fields(_MemoryState):
        collection = getattr(decoded, field.name)
        if type(collection) is not dict:
            raise CLIStateError(f"Invalid MemoryStore collection: {field.name}")
        if not _matches_state_type(collection, annotations[field.name]):
            raise CLIStateError(f"Invalid MemoryStore key/value contract: {field.name}")
    return decoded
