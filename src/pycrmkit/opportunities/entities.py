"""Opportunity aggregate root and commercial lifecycle."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pycrmkit.contacts import ContactId
from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.money import Money
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.organizations import OrganizationId


class OpportunityId(UUIDId):
    """Strongly typed identifier for an Opportunity."""


class OpportunityStatus(StrEnum):
    """Commercial outcome lifecycle independent from pipeline-stage movement."""

    OPEN = "open"
    WON = "won"
    LOST = "lost"
    CANCELLED = "cancelled"


def _normalize_required_text(value: str, *, field_name: str, max_length: int) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        raise ValidationError(
            f"{field_name} is required",
            code=f"opportunity.{field_name}.required",
        )
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"opportunity.{field_name}.too_long",
        )
    return normalized


def _normalize_optional_text(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"opportunity.{field_name}.too_long",
        )
    return normalized


def _normalize_value(
    estimated_value: Decimal | None,
    currency: str | None,
) -> tuple[Decimal | None, str | None]:
    if estimated_value is None and currency is None:
        return None, None
    if estimated_value is None:
        raise ValidationError(
            "estimated_value is required when currency is supplied",
            code="opportunity.estimated_value.required",
        )
    if currency is None:
        raise ValidationError(
            "currency is required when estimated_value is supplied",
            code="opportunity.currency.required",
        )
    money = Money(estimated_value, currency)
    return money.amount, money.currency


def _normalize_probability(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if type(value) is not Decimal:
        raise ValidationError(
            "opportunity probability must be a Decimal",
            code="opportunity.probability.decimal_required",
        )
    if not value.is_finite() or value < Decimal("0") or value > Decimal("1"):
        raise ValidationError(
            "opportunity probability must be between 0 and 1",
            code="opportunity.probability.out_of_range",
        )
    return value


@dataclass(eq=False, slots=True)
class Opportunity(TimestampedEntity[OpportunityId]):
    """Potential commercial transaction or business outcome."""

    name: str
    contact_id: ContactId
    organization_id: OrganizationId | None = None
    pipeline_id: str | None = None
    stage_id: str | None = None
    stage_entered_at: datetime | None = None
    estimated_value: Decimal | None = None
    currency: str | None = None
    probability: Decimal | None = None
    expected_close_date: date | None = None
    owner_id: str | None = None
    status: OpportunityStatus = OpportunityStatus.OPEN

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.name = _normalize_required_text(
            self.name,
            field_name="name",
            max_length=300,
        )
        if not isinstance(self.contact_id, ContactId):
            raise ValidationError(
                "opportunity contact_id must be a ContactId",
                code="opportunity.contact_id.invalid",
            )
        if self.organization_id is not None and not isinstance(
            self.organization_id, OrganizationId
        ):
            raise ValidationError(
                "opportunity organization_id must be an OrganizationId",
                code="opportunity.organization_id.invalid",
            )
        self.pipeline_id = _normalize_optional_text(
            self.pipeline_id,
            field_name="pipeline_id",
            max_length=255,
        )
        self.stage_id = _normalize_optional_text(
            self.stage_id,
            field_name="stage_id",
            max_length=255,
        )
        if self.stage_id is not None and self.pipeline_id is None:
            raise ValidationError(
                "stage_id requires pipeline_id",
                code="opportunity.stage_id.pipeline_required",
            )
        if self.stage_id is None:
            if self.stage_entered_at is not None:
                raise ValidationError(
                    "stage_entered_at requires stage_id",
                    code="opportunity.stage_entered_at.stage_required",
                )
        else:
            entered_at = self.stage_entered_at or self.created_at
            if not isinstance(entered_at, datetime):
                raise ValidationError(
                    "stage_entered_at must be a datetime",
                    code="opportunity.stage_entered_at.invalid",
                )
            entered_at = as_utc(entered_at)
            if entered_at < self.created_at:
                raise ValidationError(
                    "stage_entered_at cannot be earlier than created_at",
                    code="opportunity.stage_entered_at.before_creation",
                )
            if entered_at > self.updated_at:
                raise ValidationError(
                    "stage_entered_at cannot be later than updated_at",
                    code="opportunity.stage_entered_at.after_update",
                )
            self.stage_entered_at = entered_at
        self.estimated_value, self.currency = _normalize_value(
            self.estimated_value,
            self.currency,
        )
        self.probability = _normalize_probability(self.probability)
        if self.expected_close_date is not None and type(self.expected_close_date) is not date:
            raise ValidationError(
                "expected_close_date must be a date",
                code="opportunity.expected_close_date.invalid",
            )
        self.owner_id = _normalize_optional_text(
            self.owner_id,
            field_name="owner_id",
            max_length=255,
        )
        self.status = OpportunityStatus(self.status)

    @property
    def money(self) -> Money | None:
        """Return the estimated commercial value as a Money value object."""
        if self.estimated_value is None:
            return None
        assert self.currency is not None
        return Money(self.estimated_value, self.currency)

    @property
    def is_terminal(self) -> bool:
        return self.status is not OpportunityStatus.OPEN

    def move_to_stage(
        self,
        stage_id: str,
        *,
        probability: Decimal | None,
        at: datetime,
        outcome: OpportunityStatus | None = None,
    ) -> None:
        """Move an open opportunity after a Pipeline policy has approved the transition."""
        if self.status is not OpportunityStatus.OPEN:
            raise InvalidStateError(
                "cannot move a closed opportunity through a pipeline",
                code="opportunity.stage.transition.closed",
                context={"status": self.status.value},
            )
        if self.pipeline_id is None:
            raise InvalidStateError(
                "opportunity requires pipeline_id before stage movement",
                code="opportunity.pipeline.required",
            )
        instant = as_utc(at)
        if instant < self.created_at:
            raise ValidationError(
                "stage transition time cannot be earlier than created_at",
                code="opportunity.stage.transition.before_creation",
            )
        if self.stage_entered_at is not None and instant < self.stage_entered_at:
            raise ValidationError(
                "stage transition time cannot precede current stage entry",
                code="opportunity.stage.transition.before_current_entry",
            )
        normalized_stage = _normalize_optional_text(
            stage_id,
            field_name="stage_id",
            max_length=255,
        )
        assert normalized_stage is not None
        self.stage_id = normalized_stage.casefold()
        self.stage_entered_at = instant
        if probability is not None:
            self.probability = _normalize_probability(probability)
        if outcome is not None:
            target = OpportunityStatus(outcome)
            if target is OpportunityStatus.OPEN:
                raise ValidationError(
                    "terminal stage outcome cannot be open",
                    code="opportunity.stage.outcome.invalid",
                )
            self.status = target
        self.updated_at = instant

    def stage_duration(self, at: datetime) -> timedelta | None:
        """Return elapsed time in the current stage when the entry time is known."""
        if self.stage_entered_at is None:
            return None
        instant = as_utc(at)
        if instant < self.stage_entered_at:
            raise ValidationError(
                "stage duration endpoint cannot precede stage entry",
                code="opportunity.stage.duration.invalid",
            )
        return instant - self.stage_entered_at

    def mark_won(self, at: datetime) -> None:
        """Close an open opportunity as won."""
        self._close(OpportunityStatus.WON, at)

    def mark_lost(self, at: datetime) -> None:
        """Close an open opportunity as lost."""
        self._close(OpportunityStatus.LOST, at)

    def cancel(self, at: datetime) -> None:
        """Cancel an open opportunity without declaring a commercial outcome."""
        self._close(OpportunityStatus.CANCELLED, at)

    def _close(self, target: OpportunityStatus, at: datetime) -> None:
        instant = as_utc(at)
        if instant < self.created_at:
            raise ValidationError(
                "opportunity transition time cannot be earlier than created_at",
                code="opportunity.transition.before_creation",
            )
        if self.status is not OpportunityStatus.OPEN:
            raise InvalidStateError(
                f"cannot transition opportunity from {self.status.value} to {target.value}",
                code="opportunity.transition.invalid",
                context={"from": self.status.value, "to": target.value},
            )
        self.status = target
        self.updated_at = instant
