"""RC-05 installed-distribution qualification for the PyCRMKit V1 candidate.

This script is intentionally self-contained so CI can copy it outside the
repository and execute it with PYTHONPATH cleared against only an installed
distribution.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib import resources
from io import StringIO
from pathlib import Path

import pycrmkit
from pycrmkit.activities import ActivityParticipant
from pycrmkit.contacts import ContactEmail
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.custom_fields import CustomFieldType
from pycrmkit.exporters import CSVExporter
from pycrmkit.importers import (
    ImportPipeline,
    ImportRow,
    IterableReader,
    PersistAction,
    PersistResult,
    RequiredFieldsValidator,
)
from pycrmkit.pipelines import Stage, StageTransition
from pycrmkit.relationships import RelationshipEndpoint, RelationshipType

EXPECTED_VERSION = os.environ.get("PYCRMKIT_EXPECTED_VERSION", "1.0.0rc1")
EXPECTED_EXTRAS = {
    "sqlalchemy",
    "postgresql",
    "migrations",
    "fastapi",
    "django",
    "drf",
    "email",
    "resend",
    "dev",
}
OPTIONAL_IMPORTS = {
    "sqlalchemy",
    "alembic",
    "psycopg",
    "fastapi",
    "pydantic",
    "django",
    "rest_framework",
    "jinja2",
    "resend",
}
EXPECTED_MIGRATIONS = {
    "0001_persistence_baseline.py",
    "0002_align_repository_reference_semantics.py",
    "0003_external_identities.py",
}


class SmokePersister:
    def persist(self, row: ImportRow) -> PersistResult:
        return PersistResult(PersistAction.CREATED, entity_id=f"contact-{row.number}")


def _assert_distribution_provenance() -> None:
    package_file = Path(pycrmkit.__file__).resolve()
    repository_root = os.environ.get("PYCRMKIT_REPOSITORY_ROOT")
    if repository_root:
        root = Path(repository_root).resolve()
        if package_file.is_relative_to(root):
            raise SystemExit(
                f"PyCRMKit leaked from repository checkout: {package_file}"
            )

    distribution = importlib.metadata.distribution("pycrmkit")
    if distribution.version != EXPECTED_VERSION:
        raise SystemExit(
            f"Installed metadata version mismatch: {distribution.version!r}"
        )
    if pycrmkit.__version__ != EXPECTED_VERSION:
        raise SystemExit(
            f"Runtime version mismatch: {pycrmkit.__version__!r}"
        )

    extras = set(distribution.metadata.get_all("Provides-Extra") or ())
    missing_extras = sorted(EXPECTED_EXTRAS - extras)
    if missing_extras:
        raise SystemExit(f"Missing optional extras in wheel metadata: {missing_extras}")

    requires_python = distribution.metadata.get("Requires-Python", "")
    if ">=3.11" not in requires_python or "<3.14" not in requires_python:
        raise SystemExit(f"Unexpected Requires-Python metadata: {requires_python!r}")

    console_scripts = {
        entry.name: entry.value
        for entry in distribution.entry_points
        if entry.group == "console_scripts"
    }
    expected_script = "pycrmkit.storage.sqlalchemy.migrations.cli:main"
    if console_scripts.get("pycrmkit-migrate") != expected_script:
        raise SystemExit(
            "Installed console-script metadata does not expose pycrmkit-migrate"
        )

    package_root = resources.files("pycrmkit")
    required_resources = (
        package_root.joinpath("py.typed"),
        package_root.joinpath(
            "storage", "sqlalchemy", "migrations", "script.py.mako"
        ),
        package_root.joinpath(
            "storage", "sqlalchemy", "migrations", "README.md"
        ),
    )
    missing_resources = [
        str(resource)
        for resource in required_resources
        if not resource.is_file()
    ]
    if missing_resources:
        raise SystemExit(f"Missing installed package resources: {missing_resources}")

    versions = package_root.joinpath(
        "storage", "sqlalchemy", "migrations", "versions"
    )
    packaged_migrations = {
        child.name
        for child in versions.iterdir()
        if child.name.endswith(".py") and child.name != "__init__.py"
    }
    if packaged_migrations != EXPECTED_MIGRATIONS:
        raise SystemExit(
            "Packaged Alembic revisions differ from V1 contract: "
            f"{sorted(packaged_migrations)}"
        )


def _assert_dependency_boundary() -> None:
    core_only = os.environ.get("PYCRMKIT_EXPECT_CORE_ONLY") == "1"
    require_optionals = os.environ.get("PYCRMKIT_REQUIRE_OPTIONALS") == "1"

    if core_only and require_optionals:
        raise SystemExit("Conflicting artifact smoke modes")

    if core_only:
        leaked = sorted(
            module
            for module in OPTIONAL_IMPORTS
            if importlib.util.find_spec(module) is not None
        )
        if leaked:
            raise SystemExit(
                f"Core-only wheel unexpectedly sees optional dependencies: {leaked}"
            )

    if require_optionals:
        missing: list[str] = []
        for module in sorted(OPTIONAL_IMPORTS):
            try:
                importlib.import_module(module)
            except ModuleNotFoundError:
                missing.append(module)
        if missing:
            raise SystemExit(f"Full-extra wheel is missing imports: {missing}")


def _run_public_v1_journey() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 14, 0, tzinfo=UTC))
    crm = pycrmkit.CRM.memory(clock=clock).with_context(
        actor_id="rc05-installed-artifact",
        correlation_id="rc05-installed-artifact",
    )

    contact = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(ContactEmail("ada@example.test", is_primary=True),),
    )
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )
    relationship = crm.relationships.create(
        source=RelationshipEndpoint.contact(contact.id),
        target=RelationshipEndpoint.organization(organization.id),
        relationship_type=RelationshipType("employment"),
        role="founder",
        is_primary=True,
    )

    contact_ref = EntityReference("contact", contact.id)
    organization_ref = EntityReference("organization", organization.id)

    activity = crm.activities.log(
        type="meeting",
        subject="Installed artifact qualification",
        participants=(ActivityParticipant(contact_ref, is_primary=True),),
        references=(organization_ref,),
    )
    clock.advance(timedelta(minutes=1))
    task = crm.tasks.create(
        title="Prepare V1 proposal",
        priority="high",
        references=(contact_ref, organization_ref),
    )
    crm.tasks.start(task.id)
    completed_task = crm.tasks.complete(task.id)

    tag = crm.tags.create("V1 Qualified")
    crm.tags.assign(tag.id, contact_ref)
    field = crm.custom_fields.define(
        key="segment",
        label="Segment",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )
    crm.custom_fields.set_value(field.id, contact_ref, "enterprise")

    identity = crm.external_identities.attach(
        contact,
        system="legacy_crm",
        external_id="ada-rc05",
        metadata={"qualification": "installed-artifact"},
    )
    if crm.external_identities.resolve("LEGACY_CRM", "ada-rc05") != identity:
        raise SystemExit("External Identity public API smoke failed")

    crm.pipelines.define(
        id="installed-artifact-sales",
        name="Installed Artifact Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
            Stage("won", "Won", 20, terminal=True, outcome="won"),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "won"),
        ),
    )
    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="rc05",
    )
    lead = crm.leads.qualify(lead.id)
    opportunity = crm.leads.convert(
        lead.id,
        name="V1 installed distribution",
        estimated_value=Decimal("42000"),
        currency="EUR",
        pipeline_id="installed-artifact-sales",
        idempotency_key="rc05-installed-conversion",
    )
    opportunity = crm.opportunities.move(opportunity.id, to="qualified")
    opportunity = crm.opportunities.move(opportunity.id, to="won")

    if opportunity.status.value != "won":
        raise SystemExit("Sales lifecycle smoke failed")
    if crm.relationships.get(relationship.id) != relationship:
        raise SystemExit("Relationship reload smoke failed")
    if crm.activities.get(activity.id) != activity:
        raise SystemExit("Activity reload smoke failed")
    if crm.tasks.get(task.id) != completed_task:
        raise SystemExit("Task lifecycle smoke failed")
    if crm.tags.list_for_entity(contact_ref).items != (tag,):
        raise SystemExit("Tag public API smoke failed")
    if crm.custom_fields.get_value(field.id, contact_ref).value != "enterprise":
        raise SystemExit("Custom Field public API smoke failed")

    timeline_types = {
        str(item.event_type)
        for item in crm.timeline.for_contact(contact.id).items
    }
    required_timeline = {
        "activity.created",
        "task.created",
        "task.started",
        "task.completed",
    }
    if not required_timeline <= timeline_types:
        raise SystemExit(
            f"Timeline smoke missing events: {sorted(required_timeline - timeline_types)}"
        )

    audits = crm.audit.by_correlation("rc05-installed-artifact")
    if audits.total < 10:
        raise SystemExit(f"Audit correlation smoke too small: {audits.total}")

    report = ImportPipeline(
        reader=IterableReader(({"email": "installed@example.test"},)),
        validator=RequiredFieldsValidator(("email",)),
        persister=SmokePersister(),
    ).run()
    if report.rows_created != 1 or report.rows_read != 1:
        raise SystemExit("Import framework smoke failed")

    stream = StringIO()
    count = CSVExporter(stream).write(
        ({"id": str(contact.id), "display_name": contact.display_name},)
    )
    if count != 1 or "Ada Lovelace" not in stream.getvalue():
        raise SystemExit("Export framework smoke failed")


def main() -> None:
    _assert_distribution_provenance()
    _assert_dependency_boundary()
    _run_public_v1_journey()
    print(
        "PyCRMKit installed-distribution V1 smoke: PASS "
        f"(version={pycrmkit.__version__}, file={Path(pycrmkit.__file__).resolve()})"
    )


if __name__ == "__main__":
    main()
