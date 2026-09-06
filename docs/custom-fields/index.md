# Custom Fields

`0.1.0b2` introduces versioned business-defined fields and typed values without binding PyCRMKit to an ORM or JSON-schema implementation.

Supported types:

```text
string
text
integer
decimal
boolean
date
datetime
email
phone
url
enum
multi_enum
reference
json
```

A definition has a stable `CustomFieldDefinitionId` and immutable `key`/`field_type`. Every successful revision increments `schema_version`; historical revisions remain addressable through the repository contract.

Each persisted `CustomFieldValue` records the schema version that validated it.

```python
definition = fields.define(
    key="customer_tier",
    label="Customer Tier",
    field_type=CustomFieldType.ENUM,
    applies_to=("contact", "organization"),
    options=(
        CustomFieldOption("gold", "Gold"),
        CustomFieldOption("silver", "Silver"),
    ),
)

fields.set_value(
    definition.id,
    EntityReference("contact", contact.id),
    "gold",
)
```

Definitions explicitly declare the entity kinds they apply to. Reference fields may additionally restrict the kinds accepted by their value.
