from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.opportunities import Opportunity, OpportunityId, OpportunityStatus
from pycrmkit.organizations import OrganizationId

NOW = datetime(2026, 9, 9, 8, 0, tzinfo=UTC)


def make_opportunity(**overrides) -> Opportunity:
    values = {
        "id": OpportunityId(UUID("00000000-0000-4000-8000-000000004001")),
        "created_at": NOW,
        "updated_at": NOW,
        "name": "  Enterprise   renewal  ",
        "contact_id": ContactId(UUID("00000000-0000-4000-8000-000000004002")),
        "organization_id": OrganizationId(UUID("00000000-0000-4000-8000-000000004003")),
        "pipeline_id": " Sales Europe ",
        "stage_id": " Proposal ",
        "estimated_value": Decimal("25000.00"),
        "currency": " eur ",
        "probability": Decimal("0.65"),
        "expected_close_date": date(2026, 10, 31),
        "owner_id": " seller-1 ",
    }
    values.update(overrides)
    return Opportunity(**values)


def test_opportunity_normalizes_core_fields() -> None:
    opportunity = make_opportunity()
    assert opportunity.name == "Enterprise renewal"
    assert opportunity.pipeline_id == "Sales Europe"
    assert opportunity.stage_id == "Proposal"
    assert opportunity.currency == "EUR"
    assert opportunity.owner_id == "seller-1"
    assert opportunity.status is OpportunityStatus.OPEN
    assert opportunity.money is not None
    assert opportunity.money.amount == Decimal("25000.00")


def test_opportunity_allows_unvalued_unstaged_creation() -> None:
    opportunity = make_opportunity(
        pipeline_id=None,
        stage_id=None,
        estimated_value=None,
        currency=None,
        probability=None,
    )
    assert opportunity.money is None
    assert opportunity.probability is None


def test_stage_requires_pipeline() -> None:
    with pytest.raises(ValidationError) as exc:
        make_opportunity(pipeline_id=None, stage_id="proposal")
    assert exc.value.code == "opportunity.stage_id.pipeline_required"


@pytest.mark.parametrize(
    ("estimated_value", "currency", "code"),
    [
        (Decimal("10"), None, "opportunity.currency.required"),
        (None, "EUR", "opportunity.estimated_value.required"),
    ],
)
def test_value_and_currency_must_be_supplied_together(
    estimated_value,
    currency,
    code,
) -> None:
    with pytest.raises(ValidationError) as exc:
        make_opportunity(estimated_value=estimated_value, currency=currency)
    assert exc.value.code == code


def test_estimated_value_rejects_float() -> None:
    with pytest.raises(ValidationError) as exc:
        make_opportunity(estimated_value=100.0)
    assert exc.value.code == "money.amount.decimal_required"


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("1.01"), Decimal("NaN")])
def test_probability_requires_finite_unit_interval(value: Decimal) -> None:
    with pytest.raises(ValidationError) as exc:
        make_opportunity(probability=value)
    assert exc.value.code == "opportunity.probability.out_of_range"


def test_probability_rejects_float() -> None:
    with pytest.raises(ValidationError) as exc:
        make_opportunity(probability=0.5)
    assert exc.value.code == "opportunity.probability.decimal_required"


def test_expected_close_date_rejects_datetime() -> None:
    with pytest.raises(ValidationError) as exc:
        make_opportunity(expected_close_date=NOW)
    assert exc.value.code == "opportunity.expected_close_date.invalid"


@pytest.mark.parametrize(
    ("transition", "expected"),
    [
        ("mark_won", OpportunityStatus.WON),
        ("mark_lost", OpportunityStatus.LOST),
        ("cancel", OpportunityStatus.CANCELLED),
    ],
)
def test_opportunity_supports_terminal_outcomes(transition: str, expected) -> None:
    opportunity = make_opportunity()
    getattr(opportunity, transition)(NOW + timedelta(minutes=1))
    assert opportunity.status is expected
    assert opportunity.is_terminal
    assert opportunity.updated_at == NOW + timedelta(minutes=1)


def test_terminal_opportunity_rejects_second_outcome() -> None:
    opportunity = make_opportunity()
    opportunity.mark_won(NOW + timedelta(minutes=1))
    with pytest.raises(InvalidStateError) as exc:
        opportunity.mark_lost(NOW + timedelta(minutes=2))
    assert exc.value.code == "opportunity.transition.invalid"


def test_transition_rejects_timestamp_before_creation() -> None:
    opportunity = make_opportunity()
    with pytest.raises(ValidationError) as exc:
        opportunity.mark_won(NOW - timedelta(seconds=1))
    assert exc.value.code == "opportunity.transition.before_creation"
