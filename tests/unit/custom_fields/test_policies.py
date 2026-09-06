from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields.policies import validate_custom_field_value
from pycrmkit.custom_fields.value_objects import CustomFieldOption, CustomFieldType
from pycrmkit.exceptions import ValidationError

OPTIONS = (
    CustomFieldOption("gold", "Gold"),
    CustomFieldOption("silver", "Silver"),
)


def validate(field_type: CustomFieldType, value: object, **kwargs: object) -> object:
    return validate_custom_field_value(
        field_type=field_type,
        value=value,
        required=bool(kwargs.get("required", False)),
        options=kwargs.get("options", ()),  # type: ignore[arg-type]
        reference_kinds=kwargs.get("reference_kinds", ()),  # type: ignore[arg-type]
    )


def test_string_text_integer_decimal_boolean_date() -> None:
    assert validate(CustomFieldType.STRING, "  Hello   World ") == "Hello World"
    assert validate(CustomFieldType.TEXT, "  A\nB  ") == "A\nB"
    assert validate(CustomFieldType.INTEGER, 42) == 42
    assert validate(CustomFieldType.DECIMAL, Decimal("19.99")) == Decimal("19.99")
    assert validate(CustomFieldType.BOOLEAN, True) is True
    assert validate(CustomFieldType.DATE, date(2026, 9, 6)) == date(2026, 9, 6)


def test_datetime_is_normalized_to_utc() -> None:
    value = datetime(2026, 9, 6, 18, tzinfo=timezone(timedelta(hours=2)))
    assert validate(CustomFieldType.DATETIME, value) == datetime(2026, 9, 6, 16, tzinfo=UTC)


def test_email_phone_url_normalize() -> None:
    assert validate(CustomFieldType.EMAIL, "User@Example.COM") == "user@example.com"
    assert validate(CustomFieldType.PHONE, "+33 6 12 34 56 78") == "+33612345678"
    assert validate(CustomFieldType.URL, "https://example.com/path") == "https://example.com/path"


def test_enum_and_multi_enum_validate_options() -> None:
    assert validate(CustomFieldType.ENUM, "Gold", options=OPTIONS) == "gold"
    assert validate(CustomFieldType.MULTI_ENUM, ["Gold", "silver"], options=OPTIONS) == (
        "gold",
        "silver",
    )
    with pytest.raises(ValidationError):
        validate(CustomFieldType.ENUM, "bronze", options=OPTIONS)
    with pytest.raises(ValidationError):
        validate(CustomFieldType.MULTI_ENUM, ["gold", "gold"], options=OPTIONS)


def test_reference_enforces_allowed_kinds() -> None:
    contact = EntityReference("contact", EntityId(UUID(int=1)))
    assert validate(
        CustomFieldType.REFERENCE,
        contact,
        reference_kinds=("contact",),
    ) == contact
    with pytest.raises(ValidationError):
        validate(
            CustomFieldType.REFERENCE,
            EntityReference("organization", EntityId(UUID(int=2))),
            reference_kinds=("contact",),
        )


def test_json_is_defensively_copied_and_validated() -> None:
    source = {"scores": [1, 2], "enabled": True}
    result = validate(CustomFieldType.JSON, source)
    assert result == source
    assert result is not source
    with pytest.raises(ValidationError):
        validate(CustomFieldType.JSON, {"amount": Decimal("1.0")})


@pytest.mark.parametrize(
    ("field_type", "value"),
    [
        (CustomFieldType.INTEGER, True),
        (CustomFieldType.DECIMAL, 1.5),
        (CustomFieldType.BOOLEAN, 1),
        (CustomFieldType.DATE, datetime(2026, 9, 6, tzinfo=UTC)),
        (CustomFieldType.DATETIME, datetime(2026, 9, 6)),
        (CustomFieldType.URL, "example.com"),
    ],
)
def test_invalid_values_are_rejected(field_type: CustomFieldType, value: object) -> None:
    with pytest.raises(ValidationError):
        validate(field_type, value)


def test_required_rejects_none() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate(CustomFieldType.STRING, None, required=True)
    assert exc_info.value.code == "custom_field.value.required"
