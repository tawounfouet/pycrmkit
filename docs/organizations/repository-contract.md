# OrganizationRepository Contract

`OrganizationRepository` is a domain-oriented protocol and never leaks an ORM/query implementation.

```python
class OrganizationRepository(Protocol):
    def get(self, organization_id: OrganizationId) -> Organization: ...
    def find(self, organization_id: OrganizationId) -> Organization | None: ...
    def save(self, organization: Organization) -> None: ...
    def archive(self, organization_id: OrganizationId, archived_at: datetime) -> Organization: ...
    def search(self, query: OrganizationQuery, page: OffsetPageRequest) -> Page[Organization]: ...
```

## Query semantics

`OrganizationQuery` supports status, normalized domain, name, registration number, owner, source, and explicit archive inclusion.

Pagination is offset based with exact counts and deterministic default ordering: `created_at ASC, id ASC`.

The reusable conformance suite lives in `tests/contracts/organizations_repository.py` and will be replayed unchanged against future Memory, SQLAlchemy, and Django adapters.
