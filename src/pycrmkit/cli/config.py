"""Declarative configuration and environment loader for PyCRMKit CLI.

Supports:
- Hierarchical resolution: CLI option > OS environment > .env > pycrm.yml > defaults
- Automatic dotenv discovery and loading (.env, infra/envs/.env, ~/.pycrmkit/.env)
- Zero-dependency fallback dotenv parser when python-dotenv is not installed
- Declarative YAML configuration (pycrm.yml, pycrm.yaml, pycrmkit.yml, .pycrm.yml)
- Environment profile support (PYCRMKIT_ENV=dev -> pycrm.yml.dev or .env.dev)
- Variable substitution (${VAR} or ${VAR:-default}) in YAML configuration
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_FILES: tuple[str, ...] = (
    "pycrm.yml",
    "pycrm.yaml",
    "pycrmkit.yml",
    "pycrmkit.yaml",
    ".pycrm.yml",
    ".pycrm.yaml",
)

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}")
_PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass
class DatabaseConfig:
    backend: str = "postgresql"
    url: str | None = None
    url_env: str = "DATABASE_URL"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


@dataclass
class RuntimeConfig:
    actor_id: str = "cli-operator"
    environment: str = "development"


@dataclass
class EmailIntegrationConfig:
    provider: str = "mock"
    api_key_env: str = "RESEND_API_KEY"
    default_sender: str | None = None


@dataclass
class WebhookIntegrationConfig:
    signing_secret_env: str = "CRM_SIGNING_SECRET"


@dataclass
class IntegrationsConfig:
    email: EmailIntegrationConfig = field(default_factory=EmailIntegrationConfig)
    webhooks: WebhookIntegrationConfig = field(default_factory=WebhookIntegrationConfig)


@dataclass
class CLIConfig:
    version: str = "1.0"
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    source: str = "default"
    config_path: Path | None = None


def _substitute_env_vars(text: str) -> str:
    """Replace ${VAR} or ${VAR:-default} with environment values."""

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default_val = match.group(2) if match.group(2) is not None else ""
        return os.environ.get(var_name, default_val)

    return _ENV_VAR_PATTERN.sub(_replacer, text)


def _deep_substitute(obj: Any) -> Any:
    """Recursively expand environment variables in parsed YAML structures."""
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _deep_substitute(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_substitute(elem) for elem in obj]
    return obj


def _parse_simple_dotenv_line(line: str) -> tuple[str, str] | None:
    """Extract key-value from a dotenv line without external dependencies."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].strip()
    if "=" not in stripped:
        return None
    key, sep, value = stripped.partition("=")
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return key, value


def find_dotenv_file(cwd: Path | None = None) -> Path | None:
    """Discover deterministic .env file locations."""
    base = cwd or Path.cwd()
    profile = os.getenv("PYCRMKIT_ENV") or os.getenv("CRM_ENV")
    candidates: list[Path] = []

    if profile and _PROFILE_NAME_PATTERN.fullmatch(profile.strip()):
        prof = profile.strip()
        candidates.extend(
            [
                base / "infra" / "envs" / f".env.{prof}",
                base / "envs" / f".env.{prof}",
                base / f".env.{prof}",
            ]
        )

    candidates.extend(
        [
            base / ".env",
            base / "infra" / "envs" / ".env",
            Path.home() / ".pycrmkit" / ".env",
        ]
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def load_local_dotenv(
    dotenv_path: Path | None = None, override: bool = False
) -> tuple[Path | None, int]:
    """Load dotenv variables with python-dotenv or lightweight stdlib fallback."""
    target = dotenv_path or find_dotenv_file()
    if target is None or not target.is_file():
        return None, 0

    count = 0
    # Prefer python-dotenv if installed
    try:
        from dotenv import dotenv_values

        values = dotenv_values(target)
        for k, v in values.items():
            if k and v is not None:
                if override or k not in os.environ:
                    os.environ[k] = str(v)
                    count += 1
        return target, count
    except ImportError:
        pass

    # Zero-dependency fallback parser
    try:
        with open(target, encoding="utf-8") as f:
            for line in f:
                pair = _parse_simple_dotenv_line(line)
                if pair:
                    k, v = pair
                    if override or k not in os.environ:
                        os.environ[k] = v
                        count += 1
        return target, count
    except OSError:
        return target, 0


def find_config_file(
    explicit_path: Path | str | None = None, cwd: Path | None = None
) -> Path | None:
    """Find declarative YAML configuration file."""
    if explicit_path:
        p = Path(explicit_path)
        if p.is_file():
            return p.resolve()
        return None

    env_config = os.getenv("PYCRMKIT_CONFIG") or os.getenv("CRM_CONFIG")
    if env_config:
        p = Path(env_config.strip())
        if p.is_file():
            return p.resolve()

    base = cwd or Path.cwd()
    profile = os.getenv("PYCRMKIT_ENV") or os.getenv("CRM_ENV")
    candidates: list[Path] = []

    if profile and _PROFILE_NAME_PATTERN.fullmatch(profile.strip()):
        prof = profile.strip()
        candidates.extend(
            [
                base / f"pycrm.yml.{prof}",
                base / f"pycrm.{prof}.yml",
                base / f"pycrmkit.yml.{prof}",
            ]
        )

    for filename in DEFAULT_CONFIG_FILES:
        candidates.append(base / filename)

    candidates.extend(
        [
            Path.home() / ".pycrmkit" / "pycrm.yml",
            Path.home() / ".pycrmkit" / "pycrm.yaml",
        ]
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def load_yaml_config(
    config_path: Path | None = None, explicit_path: Path | str | None = None
) -> CLIConfig:
    """Load and parse YAML configuration into a structured CLIConfig object."""
    target = config_path or find_config_file(explicit_path=explicit_path)
    if target is None or not target.is_file():
        return CLIConfig(source="default")

    try:
        import yaml
    except ImportError:
        # Fallback if PyYAML not installed: report file found but unparsed
        return CLIConfig(source="unparsed", config_path=target)

    try:
        with open(target, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception:
        return CLIConfig(source="error", config_path=target)

    if not isinstance(raw, dict):
        return CLIConfig(source="empty", config_path=target)

    expanded = _deep_substitute(raw)

    runtime_data = expanded.get("runtime", {}) or {}
    database_data = expanded.get("database", {}) or {}
    integrations_data = expanded.get("integrations", {}) or {}
    email_data = integrations_data.get("email", {}) or {}
    webhooks_data = integrations_data.get("webhooks", {}) or {}

    runtime = RuntimeConfig(
        actor_id=runtime_data.get("actor_id", "cli-operator"),
        environment=runtime_data.get("environment", "development"),
    )

    database = DatabaseConfig(
        backend=database_data.get("backend", "postgresql"),
        url=database_data.get("url"),
        url_env=database_data.get("url_env", "DATABASE_URL"),
        pool_size=int(database_data.get("pool_size", 5)),
        max_overflow=int(database_data.get("max_overflow", 10)),
        echo=bool(database_data.get("echo", False)),
    )

    integrations = IntegrationsConfig(
        email=EmailIntegrationConfig(
            provider=email_data.get("provider", "mock"),
            api_key_env=email_data.get("api_key_env", "RESEND_API_KEY"),
            default_sender=email_data.get("default_sender"),
        ),
        webhooks=WebhookIntegrationConfig(
            signing_secret_env=webhooks_data.get("signing_secret_env", "CRM_SIGNING_SECRET"),
        ),
    )

    return CLIConfig(
        version=str(expanded.get("version", "1.0")),
        runtime=runtime,
        database=database,
        integrations=integrations,
        source="file",
        config_path=target,
    )


def resolve_database_url() -> tuple[str | None, str]:
    """Resolve database URL following the resolution hierarchy:

    1. OS environment: PYCRMKIT_DATABASE_URL
    2. OS environment: DATABASE_URL
    3. YAML config file: database.url
    4. YAML config file: env var referenced in database.url_env
    5. In-memory / local fallback
    """
    if "PYTEST_CURRENT_TEST" in os.environ and not os.getenv("PYCRMKIT_TEST_ENABLE_ENV"):
        return None, "pytest:in-memory"

    if os.getenv("PYCRMKIT_DATABASE_URL"):
        return os.getenv("PYCRMKIT_DATABASE_URL"), "env:PYCRMKIT_DATABASE_URL"

    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL"), "env:DATABASE_URL"

    cfg = load_yaml_config()
    if cfg.source == "file":
        if cfg.database.url:
            return cfg.database.url, f"config:{cfg.config_path.name if cfg.config_path else 'pycrm.yml'}"
        if cfg.database.url_env and os.getenv(cfg.database.url_env):
            return os.getenv(cfg.database.url_env), f"env:{cfg.database.url_env}"

    return None, "default:in-memory"


def resolve_actor_id() -> tuple[str, str]:
    """Resolve default audit trail actor ID."""
    if os.getenv("CRM_ACTOR_ID"):
        return os.getenv("CRM_ACTOR_ID", "cli-operator"), "env:CRM_ACTOR_ID"

    cfg = load_yaml_config()
    if cfg.source == "file" and cfg.runtime.actor_id:
        return cfg.runtime.actor_id, f"config:{cfg.config_path.name if cfg.config_path else 'pycrm.yml'}"

    return "cli-operator", "default"
