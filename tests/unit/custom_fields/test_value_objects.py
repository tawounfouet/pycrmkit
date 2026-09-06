from pycrmkit.custom_fields.value_objects import (
    CustomFieldOption,
    CustomFieldType,
    normalize_custom_field_key,
)


def test_all_required_custom_field_types_exist() -> None:
    assert {field_type.value for field_type in CustomFieldType} == {
        "string",
        "text",
        "integer",
        "decimal",
        "boolean",
        "date",
        "datetime",
        "email",
        "phone",
        "url",
        "enum",
        "multi_enum",
        "reference",
        "json",
    }


def test_field_key_and_option_codes_normalize() -> None:
    assert normalize_custom_field_key("Customer Segment") == "customer_segment"
    option = CustomFieldOption("Very Important", "Very Important")
    assert option.code == "very-important"
