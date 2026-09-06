# Organizations

Version `0.1.0a3` introduces the Organization vertical slice alongside Contacts.

## Domain shape

```text
Organization value objects
        ↓
Organization aggregate
        ↓
OrganizationService
        ↓
OrganizationRepository Protocol
        ↓
Adapters (Memory later, SQLAlchemy/Django later)
```

The production Memory adapter is intentionally deferred. The contract suite executes against a test-only reference repository.

## Organization identity

An Organization has a required legal name and may carry a trading name, custom display name, registration number, tax identifier, domains, addresses, owner, source, metadata, and lifecycle status.

Display-name precedence is deterministic: explicit display name → trading name → legal name.

```python
from pycrmkit.organizations import OrganizationDomain, OrganizationService

service = OrganizationService(repository=my_repository)
organization = service.create(
    legal_name="Example Holdings SAS",
    trading_name="Example CRM",
    registration_number="123 456 789",
    domains=(OrganizationDomain("example.com", is_primary=True),),
)
```

## Domains

`OrganizationDomain` accepts bare DNS names only. It normalizes case, a trailing dot, and internationalized labels through IDNA, without accepting URL schemes, paths, or email addresses.

## Repository contract

Every adapter must implement identical observable semantics for `get`, `find`, `save`, `archive`, and `search`. Archived organizations are hidden by default; ordering is `created_at ASC, id ASC`; pagination returns exact counts.
