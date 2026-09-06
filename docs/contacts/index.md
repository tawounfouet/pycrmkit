# Contacts

Version `0.1.0a2` introduces the first complete CRM vertical slice: the Contact domain.

```text
Contact value objects
        ↓
Contact aggregate
        ↓
ContactService
        ↓
ContactRepository Protocol
        ↓
Adapters
```

The production Memory adapter is **not** part of this milestone. The test suite contains a test-only reference repository solely to execute the shared repository contract.

## Value objects

```python
from pycrmkit.contacts import Address, ContactEmail, ContactPhone

email = ContactEmail("Thomas@Example.com", is_primary=True)
phone = ContactPhone("+33 6 12 34 56 78")
address = Address(
    line1="27 rue du Faubourg du Temple",
    city="Paris",
    postal_code="75010",
    country_code="FR",
)
```

Phone normalization removes common separators but never guesses a missing country code.

## Contact service

```python
from pycrmkit.contacts import ContactEmail, ContactService, ContactUpdate

service = ContactService(repository=my_repository)
contact = service.create(
    first_name="Thomas",
    emails=(ContactEmail("thomas@example.com", is_primary=True),),
)
contact = service.update(contact.id, ContactUpdate(last_name="Awounfouet"))
service.archive(contact.id)
```

Every adapter must implement the same `ContactRepository` observable semantics. The reusable suite lives in `tests/contracts/contacts_repository.py`.
