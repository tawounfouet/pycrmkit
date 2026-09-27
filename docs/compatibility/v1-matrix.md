# V1 Compatibility Matrix

PyCRMKit `1.0.0b3` publishes the compatibility matrix intended for the V1
production contract.

A version is **qualified** only when:

```text
package metadata permits installation
        +
dedicated compatibility CI executes the relevant tests
        +
the combination passes
```

Installability alone is not treated as a support promise.

## Supported Python versions

| Python | V1 status |
| --- | --- |
| 3.11 | Qualified |
| 3.12 | Qualified |
| 3.13 | Qualified |
| 3.14+ | Not qualified by 1.0.0b3 |

Package metadata therefore uses:

```text
Requires-Python: >=3.11,<3.14
```

All three supported minors execute the public compatibility manifest and package
smoke tests.

## PostgreSQL

The production-reference server matrix is:

| PostgreSQL | V1 status |
| --- | --- |
| 16 | Qualified |
| 17 | Qualified |
| earlier | Not qualified by 1.0.0b3 |
| later | Not yet qualified |

Each PostgreSQL version is crossed with both qualified SQLAlchemy families.

## SQLAlchemy and psycopg

| Dependency | Qualified families | Install specifier |
| --- | --- | --- |
| SQLAlchemy | 2.0.x, 2.1.x | `>=2.0,<2.2` |
| psycopg | 3.2.x, 3.3.x | `>=3.2,<3.4` |

The persistence compatibility gate executes the full cross-product:

```text
PostgreSQL 16 / 17
    × SQLAlchemy 2.0 / 2.1
    × psycopg 3.2 / 3.3
    = 8 qualified persistence cells
```

For each cell it runs PostgreSQL adapter tests, migration qualification and
SQLAlchemy repository contracts.

## FastAPI / Pydantic

| Dependency | Qualified family | Install specifier |
| --- | --- | --- |
| FastAPI | 0.141.x | `>=0.141,<0.142` |
| Pydantic | 2.13.x | `>=2.13,<2.14` |

The transport integration is replayed on the supported Python edge minors:

```text
Python 3.11
Python 3.13
```

The normal Python matrix separately covers 3.12.

## Django / Django REST Framework

| Dependency | Qualified family | Install specifier |
| --- | --- | --- |
| Django | 5.2.x LTS | `>=5.2,<5.3` |
| Django REST Framework | 3.18.x | `>=3.18,<3.19` |

The Django and DRF integration suites are replayed on:

```text
Python 3.11
Python 3.13
```

The production-reference Django/PostgreSQL E2E remains an independent mandatory
release gate.

## Provider extras

| Extra | Qualified dependency family |
| --- | --- |
| `email` | Jinja2 3.1.x |
| `resend` | Resend 2.x from 2.47 |

Jinja2 is constrained to:

```text
>=3.1,<3.2
```

The Resend provider remains constrained to:

```text
>=2.47,<3
```

## Qualified optional dependency combinations

The dedicated matrix verifies installation and import boundaries for:

```text
core
sqlalchemy
postgresql
migrations
fastapi
django
drf
email
resend
fastapi + postgresql + migrations
django + drf + postgresql
```

The last two combinations are the reference composite application stacks.

## Machine-readable contract

The source of truth is:

```text
tests/compatibility/compatibility_matrix_v1.json
```

It is checked against `pyproject.toml` by:

```text
tests/compatibility/test_compatibility_matrix_v1.py
```

The contract verifies that package metadata does not silently drift away from
the published support policy.

## Dedicated CI

The workflow:

```text
.github/workflows/compatibility-matrix.yml
```

contains these independent jobs:

```text
Python matrix
PostgreSQL × SQLAlchemy matrix
FastAPI/Pydantic edge-Python matrix
Django/DRF edge-Python matrix
optional-extra combination matrix
```

`fail-fast: false` is used so a compatibility failure exposes the complete set
of affected cells instead of stopping after the first failure.

## Support semantics

**Qualified** means the exact family/range has release evidence in this matrix.

It does not mean every future patch/minor inside an unconstrained major is
automatically supported.

For example:

```text
Django 5.2.x  → qualified
Django 6.x    → not implicitly supported

FastAPI 0.141.x → qualified
FastAPI 0.142+  → requires a future qualification change

Python 3.13 → qualified
Python 3.14 → requires a future qualification change
```

This policy intentionally favors deterministic V1 support over permissive
future dependency resolution.

## Scope boundary

The matrix does not claim support for:

```text
alternative Python implementations
PostgreSQL versions outside 16/17
SQLAlchemy 1.x
Django outside 5.2.x
DRF outside 3.18.x
FastAPI outside 0.141.x
unlisted optional-extra combinations
```

Those combinations may work, but they are outside the V1 qualified contract
until explicitly added to the matrix.

The next milestone is:

```text
1.0.0rc1 — Full Production Qualification
```
