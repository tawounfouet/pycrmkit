# Declarative Configuration & Environment Architecture

PyCRMKit provides a streamlined, zero-friction developer experience inspired by **dbt** and **pyingestkit**. Instead of requiring manual shell exports (`export DATABASE_URL=...`) across different terminal sessions, the CLI (`pck`), migrations engine, and tests automatically resolve their configuration.

---

## 1. Resolution Hierarchy

When executing CLI commands or initializing storage backends, PyCRMKit resolves configuration following a strict precedence hierarchy:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CLI Options / Command-line arguments                     │
│    (e.g., pck migrate upgrade --database-url=...)           │
├─────────────────────────────────────────────────────────────┤
│ 2. OS Environment Variables                                 │
│    (Explicit shell exports: PYCRMKIT_DATABASE_URL, etc.)    │
├─────────────────────────────────────────────────────────────┤
│ 3. Local Dotenv Files (.env)                                │
│    (.env, infra/envs/.env, ~/.pycrmkit/.env)                │
├─────────────────────────────────────────────────────────────┤
│ 4. Declarative YAML Configuration (pycrm.yml)               │
│    (pycrm.yml, pycrm.yaml, pycrm.yml.{profile})             │
├─────────────────────────────────────────────────────────────┤
│ 5. Safe Defaults / In-Memory Store                          │
│    (Zero-dependency local store: ~/.pycrmkit/crm_state.db)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Declarative Configuration File (`pycrm.yml`)

Create a `pycrm.yml` file at the root of your project or in `~/.pycrmkit/pycrm.yml`:

```yaml
# pycrm.yml - PyCRMKit Declarative Configuration
version: "1.0"

# Operator & Audit Context
runtime:
  actor_id: "thomas@webtech.agency"
  environment: "development" # development | staging | production

# Database Persistence Engine
database:
  backend: "postgresql" # postgresql | sqlite | memory
  url: "postgresql+psycopg:///pycrm"
  pool_size: 5
  max_overflow: 10
  echo: false

# External Providers & Integrations
integrations:
  email:
    provider: "resend" # resend | mock | smtp
    api_key_env: "RESEND_API_KEY"
    default_sender: "contact@webtech.agency"

  webhooks:
    signing_secret_env: "CRM_SIGNING_SECRET"

# CLI Presentation
cli:
  format: "rich" # rich | json | plain
```

### Environment Profiles

Like `pyingestkit` (`pyingest.yml.dev`, `pyingest.yml.prod`), PyCRMKit supports active environment profiles via the `PYCRMKIT_ENV` environment variable:

```bash
# Automatically loads pycrm.yml.prod or .env.prod
export PYCRMKIT_ENV=prod
pck doctor
```

---

## 3. Environment Variables (`.env`)

For sensitive secrets and local credential overrides, PyCRMKit auto-loads `.env` from the project root:

```ini
# .env
DATABASE_URL="postgresql+psycopg:///pycrm"
PYCRMKIT_DATABASE_URL="postgresql+psycopg:///pycrm"
CRM_ACTOR_ID="thomas@webtech.agency"
CRM_SIGNING_SECRET="dev-signing-secret-key-32chars"
RESEND_API_KEY="re_123456789_dev"
```

> **Zero Extra Dependency Guarantee**: PyCRMKit will use `python-dotenv` if installed, or smoothly fall back to its internal lightweight `.env` parser if running in a minimal environment.

---

## 4. Diagnostics with `pck doctor`

To inspect the currently active configuration and test your live database connection:

```bash
pck doctor
```

Output:
```
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Category      ┃ Check                   ┃ Status ┃ Details                   ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Configuration │ Config File (YAML)      │ ✓ PASS │ pycrm.yml                 │
│ Configuration │ Environment File (.env) │ ✓ PASS │ .env                      │
│ Runtime       │ Python Version          │ ✓ PASS │ 3.11.15                   │
│ Engine        │ In-Memory CRM Core      │ ✓ PASS │ Operational               │
│ Environment   │ DATABASE_URL            │  SET   │ pos...crm [PostgreSQL]    │
│ Environment   │ CRM_ACTOR_ID            │  SET   │ tho...ncy [Audit actor]   │
│ Storage       │ PostgreSQL Live Ping    │ ✓ PASS │ Connected (48 tables)     │
└───────────────┴─────────────────────────┴────────┴───────────────────────────┘
```

---

## Explicit demo-write policy (v1.3 development, AUD-FIX-03)

The `seed` command is a demonstration tool, not a production data loader. When a persistent
SQLAlchemy database is configured, `pck seed` refuses to write by default. Select the
local store with `pck seed --local`, or, in a non-production environment only, explicitly
authorize the configured persistent target with `pck seed --database --yes`.

`pck dashboard --demo` runs on a fresh, ephemeral Memory adapter. It does not seed the
configured SQLAlchemy database or write to the local state file. Ordinary dashboard
reads use the configured backend.

Malformed YAML, a missing explicitly configured file, or a selected persistent backend
without a URL now results in a nonzero configuration error rather than silent fallback.
Secrets should never be printed while diagnosing configuration problems.

**Security qualification status:** AUD-FIX-03 is still under review and does not constitute
a Gate S0 approval. The legacy CLI local state uses pickle until AUD-FIX-02 is completed;
local state files must not be treated as safe for untrusted input or production customer data.


## Safe local state (AUD-FIX-02 integration)

Local CLI state is a versioned JSON document stored by default at
`~/.pycrmkit/crm_state.json` or in `PYCRMKIT_CLI_STATE_FILE`.
The serializer uses a closed PyCRMKit domain-type allowlist. It never unpickles
untrusted data or imports classes from the local document. It rejects corrupt
files and unknown schema versions instead of resetting them. State is written
atomically and protected against concurrent writers by an exclusive sibling lock.
Legacy `.pickle` state files must be archived or discarded and the trusted
sample data regenerated. See `docs/development/1.3.0/ADR-STATE-001-safe-cli-state.md`.
