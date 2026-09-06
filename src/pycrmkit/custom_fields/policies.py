"""Custom-field definition and value validation policies."""

from __future__ import annotations

import math
import re
import unicodedata
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlsplit

from pycrmkit.contacts.value_objects import normalize_email, normalize_phone
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.core.time import as_utc
from pycrmkit.custom_fields.value_objects import (
    CustomFieldOption,
    CustomFieldType,
    normalize_option_code,
)
from pycrmkit.exceptions import ValidationError

_WHITESPACE = re.compile(r"\s+")


def normalize_label(value: str) -> str:
    label = _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())
    if not label:
        raise ValidationError(
            "custom field label cannot be empty",
            code="custom_field.label.required",
        )
    if len(label) > 120:
        raise ValidationError(
            "custom field label cannot exceed 120 characters",
            code="custom_field.label.too_long",
        )
    return label


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    return normalized or None


def normalize_entity_kinds(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(normalize_entity_kind(value) for value in values)
    if not normalized:
        raise ValidationError(
            "custom fields must target at least one entity kind",
            code="custom_field.applies_to.required",
        )
    if len(set(normalized)) != len(normalized):
        raise ValidationError(
            "custom field entity kinds must be unique",
            code="custom_field.applies_to.duplicate",
        )
    return normalized


def validate_definition_shape(
    *,
    field_type: CustomFieldType,
    options: tuple[CustomFieldOption, ...],
    reference_kinds: tuple[str, ...],
) -> tuple[tuple[CustomFieldOption, ...], tuple[str, ...]]:
    option_codes = [option.code for option in options]
    if len(set(option_codes)) != len(option_codes):
        raise ValidationError(
            "custom field option codes must be unique",
            code="custom_field.option.duplicate",
        )
    if field_type in {CustomFieldType.ENUM, CustomFieldType.MULTI_ENUM}:
        if not options:
            raise ValidationError(
                "enum custom fields require at least one option",
                code="custom_field.option.required",
            )
    elif options:
        raise ValidationError(
            "options are only valid for enum custom fields",
            code="custom_field.option.not_allowed",
        )

    normalized_reference_kinds = tuple(
        normalize_entity_kind(value) for value in reference_kinds
    )
    if len(set(normalized_reference_kinds)) != len(normalized_reference_kinds):
        raise ValidationError(
            "reference kinds must be unique",
            code="custom_field.reference_kind.duplicate",
        )
    if field_type is not CustomFieldType.REFERENCE and normalized_reference_kinds:
        raise ValidationError(
            "reference kinds are only valid for reference custom fields",
            code="custom_field.reference_kind.not_allowed",
        )
    return options, normalized_reference_kinds


def validate_entity_target(entity: EntityReference, applies_to: tuple[str, ...]) -> None:
    if entity.kind not in applies_to:
        raise ValidationError(
            "custom field does not apply to this entity kind",
            code="custom_field.entity_kind.not_allowed",
            context={"entity_kind": entity.kind, "applies_to": applies_to},
        )


def _validate_json(value: object, path: str = "$") -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return deepcopy(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError(
                "JSON custom field values cannot contain non-finite floats",
                code="custom_field.value.invalid_json",
                context={"path": path},
            )
        return value
    if isinstance(value, list):
        return [_validate_json(item, f"{path}[]") for item in value]
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError(
                    "JSON custom field object keys must be strings",
                    code="custom_field.value.invalid_json",
                    context={"path": path},
                )
            result[key] = _validate_json(item, f"{path}.{key}")
        return result
    raise ValidationError(
        "custom field JSON value is not JSON-compatible",
        code="custom_field.value.invalid_json",
        context={"path": path, "type": type(value).__name__},
    )


def validate_custom_field_value(
    *,
    field_type: CustomFieldType,
    value: object,
    required: bool,
    options: tuple[CustomFieldOption, ...],
    reference_kinds: tuple[str, ...],
) -> object:
    """Validate and normalize one value according to a field definition."""
    if value is None:
        if required:
            raise ValidationError(
                "custom field value is required",
                code="custom_field.value.required",
            )
        return None

    if field_type is CustomFieldType.STRING:
        if not isinstance(value, str):
            return _wrong_type(field_type, value)
        return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())

    if field_type is CustomFieldType.TEXT:
        if not isinstance(value, str):
            return _wrong_type(field_type, value)
        return unicodedata.normalize("NFKC", value).strip()

    if field_type is CustomFieldType.INTEGER:
        if type(value) is not int:
            return _wrong_type(field_type, value)
        return value

    if field_type is CustomFieldType.DECIMAL:
        if not isinstance(value, Decimal) or not value.is_finite():
            return _wrong_type(field_type, value)
        return value

    if field_type is CustomFieldType.BOOLEAN:
        if type(value) is not bool:
            return _wrong_type(field_type, value)
        return value

    if field_type is CustomFieldType.DATE:
        if type(value) is not date:
            return _wrong_type(field_type, value)
        return value

    if field_type is CustomFieldType.DATETIME:
        if not isinstance(value, datetime):
            return _wrong_type(field_type, value)
        try:
            return as_utc(value)
        except ValueError as exc:
            raise ValidationError(
                "datetime custom field values must be timezone-aware",
                code="custom_field.value.invalid_datetime",
            ) from exc

    if field_type is CustomFieldType.EMAIL:
        if not isinstance(value, str):
            return _wrong_type(field_type, value)
        try:
            return normalize_email(value)
        except ValidationError as exc:
            raise ValidationError(
                "custom field email value is invalid",
                code="custom_field.value.invalid_email",
                context={"value": value},
            ) from exc

    if field_type is CustomFieldType.PHONE:
        if not isinstance(value, str):
            return _wrong_type(field_type, value)
        try:
            return normalize_phone(value)
        except ValidationError as exc:
            raise ValidationError(
                "custom field phone value is invalid",
                code="custom_field.value.invalid_phone",
                context={"value": value},
            ) from exc

    if field_type is CustomFieldType.URL:
        if not isinstance(value, str):
            return _wrong_type(field_type, value)
        normalized = unicodedata.normalize("NFKC", value).strip()
        parsed = urlsplit(normalized)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            raise ValidationError(
                "URL custom field values require an absolute http(s) URL",
                code="custom_field.value.invalid_url",
                context={"value": value},
            )
        return normalized

    allowed = {option.code for option in options}
    if field_type is CustomFieldType.ENUM:
        if not isinstance(value, str):
            return _wrong_type(field_type, value)
        code = normalize_option_code(value)
        if code not in allowed:
            raise ValidationError(
                "enum custom field value is not an allowed option",
                code="custom_field.value.invalid_enum",
                context={"value": code},
            )
        return code

    if field_type is CustomFieldType.MULTI_ENUM:
        if not isinstance(value, (list, tuple)):
            return _wrong_type(field_type, value)
        codes = tuple(normalize_option_code(item) for item in value if isinstance(item, str))
        if len(codes) != len(value):
            return _wrong_type(field_type, value)
        if len(set(codes)) != len(codes):
            raise ValidationError(
                "multi-enum custom field values cannot contain duplicates",
                code="custom_field.value.duplicate_enum",
            )
        invalid = [code for code in codes if code not in allowed]
        if invalid:
            raise ValidationError(
                "multi-enum custom field value contains an unknown option",
                code="custom_field.value.invalid_enum",
                context={"invalid": invalid},
            )
        return codes

    if field_type is CustomFieldType.REFERENCE:
        if not isinstance(value, EntityReference):
            return _wrong_type(field_type, value)
        if reference_kinds and value.kind not in reference_kinds:
            raise ValidationError(
                "reference custom field targets a disallowed entity kind",
                code="custom_field.value.invalid_reference_kind",
                context={"entity_kind": value.kind, "allowed": reference_kinds},
            )
        return value

    if field_type is CustomFieldType.JSON:
        return _validate_json(value)

    raise AssertionError(f"Unhandled custom field type: {field_type}")


def _wrong_type(field_type: CustomFieldType, value: object) -> object:
    raise ValidationError(
        "custom field value has the wrong Python type",
        code="custom_field.value.wrong_type",
        context={"field_type": field_type.value, "type": type(value).__name__},
    )
