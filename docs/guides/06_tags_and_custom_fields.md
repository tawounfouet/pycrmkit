# 06 - Tags & Custom Fields

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

Tags and Custom Fields extend CRM behavior without modifying the core Contact,
Organization or Relationship aggregates.

They solve different problems:

~~~text
Tag
-> reusable classification

Custom Field
-> structured business-specific data
~~~

This chapter closes LEVEL 1 - CRM Core.

## What you will build

~~~text
CRM entity
   |
   +-- Tags
   |    +-- reusable vocabulary
   |    +-- normalized names
   |    +-- assignments
   |
   +-- Custom Fields
        +-- versioned schema
        +-- typed validation
        +-- entity-kind targeting
        +-- current values
~~~

# Part I - Tags

## 1. Why Tags exist

Tags classify CRM entities without adding permanent fields to their aggregates.

Typical examples:

~~~text
VIP
Needs Follow Up
Partner
Strategic Account
High Risk
Newsletter
~~~

One Tag may be assigned to many entities:

~~~text
          +-- Contact A
          |
VIP Tag --+-- Contact B
          |
          +-- Organization C
~~~

This is more extensible than adding fields such as is_vip or is_partner to the
Contact model.

## 2. Tag model

~~~text
Tag
+-- TagId
+-- TagName
+-- metadata

TagAssignment
+-- TagAssignmentId
+-- tag_id
+-- EntityReference
~~~

TagAssignment is the link between reusable vocabulary and one CRM entity.

## 3. Create a Tag

~~~python
from pycrmkit import CRM

crm = CRM.memory()

tag = crm.tags.create("VIP Client")

print(tag.id)
print(tag.name.value)
~~~

## 4. TagName normalization

~~~python
from pycrmkit.tags import TagName

name = TagName("  VIP   Client ")

assert name.value == "VIP Client"
assert name.normalized == "vip client"
~~~

Normalization applies Unicode NFKC, trimming, whitespace collapse and case-fold
for the comparison form.

A blank Tag name raises ValidationError with code tag.name.required. Tag names
are limited to 80 characters.

## 5. Tag names are unique by normalized value

This is invalid:

~~~python
crm.tags.create("Priority")
crm.tags.create(" priority ")
~~~

Both normalize to priority, so the second call raises:

~~~text
DuplicateError
code = tag.duplicate
~~~

Tags are reusable vocabulary rather than per-record free text.

## 6. Assign a Tag through EntityReference

~~~python
from pycrmkit.core.references import EntityReference

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)

assignment = crm.tags.assign(
    tag.id,
    contact_ref,
)
~~~

The observable uniqueness key is:

~~~text
(tag_id, entity_reference)
~~~

Assigning the same Tag to the same entity twice raises DuplicateError with code
tag.assignment.duplicate.

The Tag must already exist. Assignment never creates vocabulary implicitly.

## 7. List and remove Tags

~~~python
page = crm.tags.list_for_entity(
    contact_ref,
)

assert page.items == (tag,)

assert crm.tags.remove(
    tag.id,
    contact_ref,
) is True

assert crm.tags.remove(
    tag.id,
    contact_ref,
) is False
~~~

Removal is idempotent and deletes only the assignment, not the Tag.

list_for_entity returns Tags ordered deterministically by normalized name and ID.

## 8. Search Tags

~~~python
from pycrmkit.tags import TagName, TagQuery

page = crm.tags.search(
    TagQuery(
        name=TagName(" vip client "),
    ),
)

assert page.items == (tag,)
~~~

TagQuery uses normalized exact equality and the shared
OffsetPageRequest/Page pagination contract.

## 9. Tag events and repository contract

Facade operations record:

~~~text
tag.created
tag.assigned
tag.removed
~~~

TagRepository owns normalized-name uniqueness, assignment uniqueness and
deterministic search/listing through:

~~~text
get / find
find_by_normalized
save
search
assign
remove
list_for_entity
~~~

The outer Unit of Work owns transaction commit/rollback.

# Part II - Custom Fields

## 10. Why Custom Fields exist

Custom Fields store structured business-specific data without changing core
aggregates.

Examples:

~~~text
customer_tier
account_score
annual_revenue
renewal_date
preferred_language
account_manager
implementation_profile
~~~

The model separates schema from values:

~~~text
CustomFieldDefinition
        |
        +-- key
        +-- label
        +-- field_type
        +-- applies_to
        +-- schema_version
        |
        v
CustomFieldValue
        |
        +-- definition_id
        +-- entity
        +-- schema_version
        +-- value
~~~

## 11. Define a field

~~~python
from pycrmkit.custom_fields import CustomFieldType

definition = crm.custom_fields.define(
    key="preferred_name",
    label="Preferred Name",
    field_type=CustomFieldType.STRING,
    applies_to=("contact",),
)

assert definition.schema_version == 1
~~~

## 12. Stable keys

Keys are machine identifiers. Normalization turns:

~~~text
Customer Tier
-> customer_tier

customer-tier
-> customer_tier
~~~

A valid normalized key follows:

~~~text
^[a-z][a-z0-9_]{0,63}$
~~~

Invalid keys raise custom_field.key.invalid.

Treat the key as a durable business API identifier.

## 13. applies_to targets entity kinds

Every definition targets at least one entity kind:

~~~python
definition = crm.custom_fields.define(
    key="customer_tier",
    label="Customer Tier",
    field_type=CustomFieldType.STRING,
    applies_to=(
        "contact",
        "organization",
    ),
)
~~~

The target tuple cannot be empty or contain duplicate normalized kinds.

When setting a value, the EntityReference kind must be included in applies_to.

## 14. Supported V1 types

~~~text
STRING
TEXT
INTEGER
DECIMAL
BOOLEAN
DATE
DATETIME
EMAIL
PHONE
URL
ENUM
MULTI_ENUM
REFERENCE
JSON
~~~

PyCRMKit validates and normalizes each type explicitly instead of coercing
arbitrary Python values.

## 15. Scalar validation

STRING collapses whitespace:

~~~text
"  Ada   Lovelace  "
-> "Ada Lovelace"
~~~

TEXT preserves internal text layout more closely and trims outer whitespace.

INTEGER requires an actual int and deliberately rejects bool.

DECIMAL requires a finite Decimal instead of float.

BOOLEAN requires a real bool.

DATE requires datetime.date.

DATETIME requires a timezone-aware datetime and normalizes it to UTC. Naive
datetimes raise custom_field.value.invalid_datetime.

EMAIL and PHONE reuse the Contact normalization foundations.

URL requires an absolute HTTP or HTTPS URL with a hostname.

## 16. ENUM

ENUM requires options:

~~~python
from pycrmkit.custom_fields import (
    CustomFieldOption,
    CustomFieldType,
)

tier = crm.custom_fields.define(
    key="customer_tier",
    label="Customer Tier",
    field_type=CustomFieldType.ENUM,
    applies_to=("contact", "organization"),
    options=(
        CustomFieldOption("gold", "Gold"),
        CustomFieldOption("silver", "Silver"),
        CustomFieldOption("bronze", "Bronze"),
    ),
)
~~~

Option codes normalize into lowercase hyphenated identifiers. A value must be
one of the allowed option codes.

## 17. MULTI_ENUM

MULTI_ENUM accepts a list or tuple of unique allowed codes and stores the
normalized result as a tuple.

Duplicate values raise custom_field.value.duplicate_enum.

Unknown values raise custom_field.value.invalid_enum.

## 18. REFERENCE

REFERENCE stores EntityReference:

~~~python
account_manager = crm.custom_fields.define(
    key="account_manager",
    label="Account Manager",
    field_type=CustomFieldType.REFERENCE,
    applies_to=("organization",),
    reference_kinds=("contact",),
)

crm.custom_fields.set_value(
    account_manager.id,
    organization_ref,
    contact_ref,
)
~~~

reference_kinds restricts the kinds accepted as the value. When empty, any valid
EntityReference is accepted.

## 19. JSON

JSON accepts recursively JSON-compatible data:

~~~text
None
string
boolean
integer
finite float
list
dict with string keys
~~~

Non-finite floats, non-string object keys and arbitrary Python objects are
rejected.

## 20. Definition-shape rules

Options belong only to ENUM and MULTI_ENUM, and both enum types require at least
one option.

reference_kinds belongs only to REFERENCE.

Option codes and reference kinds must be unique.

These are domain-schema rules rather than UI-only validation.

## 21. Required values

A definition may declare required=True.

When validating a value:

~~~text
required=True
value=None
-> ValidationError
custom_field.value.required
~~~

Required does not automatically backfill every existing CRM entity. Cross-entity
completeness is an application/workflow concern.

## 22. Set and read a value

~~~python
contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)

value = crm.custom_fields.set_value(
    tier.id,
    contact_ref,
    "GOLD",
)

assert value.value == "gold"
assert value.schema_version == 1

current = crm.custom_fields.get_value(
    tier.id,
    contact_ref,
)

assert current == value
~~~

The stored value records which schema revision validated it.

## 23. One current value per definition/entity pair

The logical uniqueness key is:

~~~text
definition_id
+
entity_reference
~~~

Setting the field again updates the current logical value and reuses its
CustomFieldValueId.

## 24. Remove and list values

~~~python
assert crm.custom_fields.list_values(
    contact_ref,
).total == 1

assert crm.custom_fields.remove_value(
    tier.id,
    contact_ref,
) is True

assert crm.custom_fields.remove_value(
    tier.id,
    contact_ref,
) is False
~~~

Removal is idempotent.

## 25. Versioned definitions

Definitions are revised rather than overwritten.

~~~python
from pycrmkit.custom_fields import CustomFieldDefinitionRevision

tier_v2 = crm.custom_fields.revise(
    tier.id,
    CustomFieldDefinitionRevision(
        label="CRM Customer Tier",
        options=(
            CustomFieldOption("gold", "Gold"),
            CustomFieldOption("silver", "Silver"),
            CustomFieldOption("bronze", "Bronze"),
            CustomFieldOption("platinum", "Platinum"),
        ),
    ),
)

assert tier_v2.id == tier.id
assert tier_v2.schema_version == 2
~~~

Historical revisions remain addressable:

~~~python
v1 = crm.custom_fields.get_definition(
    tier.id,
    version=1,
)

latest = crm.custom_fields.get_definition(
    tier.id,
)

assert v1.schema_version == 1
assert latest.schema_version == 2
~~~

## 26. Key and type are immutable

CustomFieldDefinitionRevision does not expose key or field_type.

That is deliberate:

~~~text
key + field_type
= schema identity
~~~

A revision may change:

~~~text
label
required
description
applies_to
options
reference_kinds
active
metadata
~~~

Every successful revision increments schema_version.

## 27. Latest schema validates new values

set_value loads the latest definition revision.

If a value already exists and the definition moves from schema version 1 to 2,
setting it again produces:

~~~text
same CustomFieldValueId
new current value
schema_version = 2
~~~

This preserves value identity while recording the schema used for validation.

## 28. Entity-kind targeting

A Contact-only definition rejects an Organization target:

~~~text
ValidationError
code = custom_field.entity_kind.not_allowed
~~~

Targeting is part of schema correctness.

## 29. Inactive definitions

A definition can be revised with active=False.

An inactive definition remains historical data but cannot accept new values:

~~~text
InvalidStateError
code = custom_field.inactive
~~~

## 30. Search definitions

~~~python
from pycrmkit.custom_fields import CustomFieldDefinitionQuery

page = crm.custom_fields.search_definitions(
    CustomFieldDefinitionQuery(
        entity_kind="contact",
    ),
)
~~~

Available filters are:

~~~text
key
field_type
entity_kind
include_inactive
~~~

Search returns the latest revision for each definition.

Inactive definitions are hidden unless include_inactive=True.

Definitions are deterministically ordered by key and ID.

## 31. Tag vs Custom Field

Use a Tag for classification:

~~~text
VIP
Partner
Needs Follow Up
Strategic Account
~~~

Use a Custom Field for typed business data:

~~~text
customer_tier = gold
annual_revenue = Decimal("1250000.50")
renewal_date = date(...)
account_manager = EntityReference(...)
~~~

A useful heuristic:

~~~text
Needs a type, validation rule or schema version?
-> Custom Field

Primarily reusable classification vocabulary?
-> Tag
~~~

## 32. Use both together

~~~text
Organization
+-- Tag: Strategic Account
+-- Tag: Partner
|
+-- Custom Field: customer_tier = gold
+-- Custom Field: annual_revenue = 1250000.50
+-- Custom Field: account_manager = contact:...
~~~

Tags provide flexible vocabulary.

Custom Fields provide controlled structured extension.

## 33. Events

Facade operations record:

~~~text
tag.created
tag.assigned
tag.removed

custom_field.defined
custom_field.revised
custom_field.value_set
custom_field.value_removed
~~~

With CRM context, these changes join the same actor/correlation audit trail as
Contacts, Organizations and Relationships.

## 34. Complete Tags example

~~~python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference
from pycrmkit.tags import TagName, TagQuery

crm = CRM.memory()

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)

vip = crm.tags.create("VIP Client")

crm.tags.assign(
    vip.id,
    contact_ref,
)

assert crm.tags.list_for_entity(
    contact_ref,
).items == (vip,)

found = crm.tags.search(
    TagQuery(
        name=TagName(" vip client "),
    ),
)

assert found.items == (vip,)

assert crm.tags.remove(
    vip.id,
    contact_ref,
) is True

assert crm.tags.remove(
    vip.id,
    contact_ref,
) is False
~~~

## 35. Complete Custom Fields example

~~~python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import (
    CustomFieldDefinitionQuery,
    CustomFieldDefinitionRevision,
    CustomFieldOption,
    CustomFieldType,
)

crm = CRM.memory()

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)
contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)

tier = crm.custom_fields.define(
    key="Customer Tier",
    label="Customer Tier",
    field_type=CustomFieldType.ENUM,
    applies_to=("contact",),
    options=(
        CustomFieldOption("gold", "Gold"),
        CustomFieldOption("silver", "Silver"),
    ),
)

assert tier.key == "customer_tier"
assert tier.schema_version == 1

value = crm.custom_fields.set_value(
    tier.id,
    contact_ref,
    "GOLD",
)

assert value.value == "gold"
assert value.schema_version == 1

tier_v2 = crm.custom_fields.revise(
    tier.id,
    CustomFieldDefinitionRevision(
        label="CRM Customer Tier",
        options=(
            CustomFieldOption("gold", "Gold"),
            CustomFieldOption("silver", "Silver"),
            CustomFieldOption("bronze", "Bronze"),
        ),
    ),
)

assert tier_v2.id == tier.id
assert tier_v2.schema_version == 2

value_v2 = crm.custom_fields.set_value(
    tier.id,
    contact_ref,
    "bronze",
)

assert value_v2.id == value.id
assert value_v2.value == "bronze"
assert value_v2.schema_version == 2

definitions = crm.custom_fields.search_definitions(
    CustomFieldDefinitionQuery(
        key="customer-tier",
    ),
)

assert definitions.items == (tier_v2,)
assert crm.custom_fields.list_values(
    contact_ref,
).items == (value_v2,)
~~~

## Common mistakes

- Creating one Tag per entity instead of reusing vocabulary.
- Treating differently cased Tag names as distinct.
- Treating duplicate Tag assignment as a no-op.
- Using Tags for typed numeric/date/reference data.
- Adding deployment-specific columns directly to Contact or Organization.
- Treating Custom Fields like an untyped JSON bag.
- Trying to mutate a custom-field key or type.
- Forgetting applies_to.
- Assuming required automatically backfills all entities.
- Passing float where DECIMAL requires Decimal.
- Passing naive datetime to DATETIME.
- Adding options to a non-enum field.
- Adding reference_kinds to a non-reference field.

## Testing extension workflows

~~~python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import CustomFieldType

def test_contact_can_receive_tag_and_custom_value() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    ref = EntityReference(
        kind="contact",
        id=contact.id,
    )

    tag = crm.tags.create("VIP")
    crm.tags.assign(tag.id, ref)

    score = crm.custom_fields.define(
        key="account_score",
        label="Account Score",
        field_type=CustomFieldType.INTEGER,
        applies_to=("contact",),
    )
    crm.custom_fields.set_value(
        score.id,
        ref,
        95,
    )

    assert crm.tags.list_for_entity(ref).items == (tag,)
    assert crm.custom_fields.get_value(
        score.id,
        ref,
    ).value == 95
~~~

## What you learned

### Tags

You can now use Tag/TagId, TagName normalization, reusable normalized
vocabulary, TagAssignment, EntityReference assignment, duplicate assignment
rejection, idempotent removal, TagQuery and TagRepository semantics.

### Custom Fields

You can now use versioned CustomFieldDefinition schemas, stable definition IDs,
immutable key/type semantics, applies_to targeting, all V1 field types,
enum/multi-enum options, reference_kinds, required validation,
CustomFieldValue identity reuse, schema-version tracking, inactive definitions,
definition search and CustomFieldRepository semantics.

## LEVEL 1 complete

~~~text
Contacts
   |
Organizations
   |
Relationships
   |
Tags
   |
Custom Fields
   v
Extensible CRM graph
~~~

The next learning level is LEVEL 2 - Customer Activity:

~~~text
07 Activities
08 Tasks
09 Timeline
~~~

That level moves from static CRM structure to interactions, work and customer
history over time.
