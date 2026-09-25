"""Event registry contract tests."""

import pytest

from pycrmkit.events import EventDefinition, EventRegistry, default_event_registry
from pycrmkit.exceptions import DuplicateError, NotFoundError, ValidationError


def test_registry_registers_resolves_and_orders_versions() -> None:
    registry = EventRegistry()
    v2 = registry.register("Contact.Created", 2)
    v1 = registry.register("contact.created", 1)

    assert str(v1.event_type) == "contact.created"
    assert registry.resolve("contact.created", 1) == v1
    assert registry.latest("CONTACT.CREATED") == v2
    assert registry.supports("contact.created", 1)
    assert registry.definitions() == (v1, v2)


def test_registry_rejects_duplicate_type_version_pair() -> None:
    registry = EventRegistry()
    registry.register("contact.created", 1)

    with pytest.raises(DuplicateError) as error:
        registry.register("contact.created", 1)

    assert error.value.code == "event.registry.definition.duplicate"


def test_registry_reports_unknown_contract() -> None:
    registry = EventRegistry()

    with pytest.raises(NotFoundError) as error:
        registry.resolve("contact.created", 1)

    assert error.value.code == "event.registry.definition.not_found"


def test_event_definition_requires_positive_schema_version() -> None:
    with pytest.raises(ValidationError) as error:
        EventDefinition("contact.created", 0)  # type: ignore[arg-type]

    assert error.value.code == "event.registry.schema_version.invalid"


def test_default_registry_covers_stable_events_through_0_4() -> None:
    registry = default_event_registry()

    for event_type in (
        "contact.created",
        "organization.updated",
        "activity.created",
        "task.completed",
        "lead.converted",
        "opportunity.won",
        "email.delivered",
    ):
        assert registry.supports(event_type, 1)

    assert len(registry) == 41
