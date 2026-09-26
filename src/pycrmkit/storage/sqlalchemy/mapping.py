"""Domain/ORM mapping contracts used by SQLAlchemy repositories."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable

DomainT = TypeVar("DomainT")
ModelT = TypeVar("ModelT")


@runtime_checkable
class SQLAlchemyMapper(Protocol[DomainT, ModelT]):
    """Explicit bidirectional mapping boundary between domain and ORM objects."""

    def to_model(self, domain: DomainT) -> ModelT:
        """Convert a domain object into its persistence representation."""
        ...

    def to_domain(self, model: ModelT) -> DomainT:
        """Rehydrate a domain object from its persistence representation."""
        ...


@dataclass(frozen=True, slots=True)
class FunctionalMapper(Generic[DomainT, ModelT]):
    """Small mapper implementation useful for bounded-context mapper modules."""

    model_factory: Callable[[DomainT], ModelT]
    domain_factory: Callable[[ModelT], DomainT]

    def to_model(self, domain: DomainT) -> ModelT:
        return self.model_factory(domain)

    def to_domain(self, model: ModelT) -> DomainT:
        return self.domain_factory(model)
