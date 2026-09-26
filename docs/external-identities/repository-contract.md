# External Identity Repository Contract

Every supported external identity repository preserves the same observable
behavior.

## Contract

```python
class ExternalIdentityRepository(Protocol):
    def find(
        self,
        system: str,
        external_id: str,
    ) -> ExternalIdentity | None: ...

    def save(
        self,
        identity: ExternalIdentity,
    ) -> None: ...

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[ExternalIdentity]: ...

    def remove(
        self,
        system: str,
        external_id: str,
    ) -> bool: ...
```

## Required semantics

```text
attach/save one identity
resolve by system + external_id
list identities for an entity
stable pagination ordering
prevent conflicting ownership
prevent duplicate mapping identity
idempotent detach
copy/isolation semantics where applicable
```

## Uniqueness

The V0.9 alpha chooses global upstream-record uniqueness:

```text
UNIQUE(system, external_id)
```

The mapped `entity_type` and `entity_id` are ownership attributes, not part
of the external-record key.

This means a single upstream record cannot silently point to two CRM entities.

## Adapter qualification

The same reusable contract is replayed against:

```text
MemoryExternalIdentityRepository
SQLAlchemyExternalIdentityRepository
DjangoExternalIdentityRepository
```

Database constraints supplement, rather than replace, the domain/service
conflict checks.
