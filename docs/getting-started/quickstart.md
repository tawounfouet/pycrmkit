# Quickstart

The current `0.1.0a2` release includes the Contact vertical slice.

```python
from pycrmkit.contacts import ContactEmail, ContactService

service = ContactService(repository=my_contact_repository)
contact = service.create(
    first_name="Thomas",
    emails=(ContactEmail("thomas@example.com", is_primary=True),),
)

print(contact.id)
print(contact.display_name)
```

`ContactRepository` is an adapter contract. A production Memory adapter arrives later in the `0.1.x` line; `0.1.0a2` intentionally does not make storage infrastructure part of the Contact domain.
