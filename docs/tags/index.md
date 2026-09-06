# Tags

`0.1.0b2` introduces reusable normalized tags that can be assigned to any CRM entity represented by `EntityReference`.

```python
from pycrmkit.core import EntityReference
from pycrmkit.tags import TagService

entity = EntityReference("contact", contact.id)
tag = service.create("VIP Client")
service.assign(tag.id, entity)
```

Tag labels preserve their human display form while exposing a case-folded normalized comparison value. Assignment uniqueness is defined by the `(tag_id, entity_reference)` pair.

Removing an assignment is idempotent and does not delete the tag itself.
