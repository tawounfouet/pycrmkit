"""Contract smoke tests for the 0.6.0a1 SQLAlchemy foundation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

pytest.importorskip("sqlalchemy")

from pycrmkit.storage.sqlalchemy import Base, FunctionalMapper, SQLAlchemyMapper  # noqa: E402
from pycrmkit.storage.sqlalchemy.models import ContactModel, WebhookDeliveryModel  # noqa: E402


def test_sqlalchemy_metadata_exposes_core_persistence_inventory() -> None:
    expected = {
        "pycrmkit_contacts",
        "pycrmkit_organizations",
        "pycrmkit_relationships",
        "pycrmkit_tags",
        "pycrmkit_custom_field_definitions",
        "pycrmkit_activities",
        "pycrmkit_tasks",
        "pycrmkit_leads",
        "pycrmkit_opportunities",
        "pycrmkit_pipelines",
        "pycrmkit_audit_entries",
        "pycrmkit_communication_intents",
        "pycrmkit_communication_records",
        "pycrmkit_webhook_subscriptions",
        "pycrmkit_webhook_deliveries",
    }

    assert expected <= set(Base.metadata.tables)


def test_metadata_has_deterministic_naming_convention() -> None:
    convention = Base.metadata.naming_convention
    assert convention is not None
    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["fk"].startswith("fk_%(table_name)s")


def test_orm_models_are_distinct_persistence_types() -> None:
    assert ContactModel.__tablename__ == "pycrmkit_contacts"
    assert WebhookDeliveryModel.__tablename__ == "pycrmkit_webhook_deliveries"


@dataclass(frozen=True)
class _Domain:
    value: str


@dataclass
class _Model:
    value: str


def test_functional_mapper_obeys_mapping_protocol() -> None:
    mapper = FunctionalMapper[_Domain, _Model](
        model_factory=lambda domain: _Model(domain.value),
        domain_factory=lambda model: _Domain(model.value),
    )

    assert isinstance(mapper, SQLAlchemyMapper)
    assert mapper.to_domain(mapper.to_model(_Domain("crm"))) == _Domain("crm")
