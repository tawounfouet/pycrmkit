from decimal import Decimal

import pytest

from pycrmkit.core import Money
from pycrmkit.exceptions import ValidationError


def test_money_requires_decimal_and_normalizes_currency() -> None:
    money = Money(Decimal("15000.00"), " eur ")
    assert money.amount == Decimal("15000.00")
    assert money.currency == "EUR"


@pytest.mark.parametrize("amount", [15000, 15000.0, "15000"])
def test_money_rejects_non_decimal_amounts(amount: object) -> None:
    with pytest.raises(ValidationError) as exc:
        Money(amount, "EUR")  # type: ignore[arg-type]
    assert exc.value.code == "money.amount.decimal_required"


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity")])
def test_money_rejects_non_finite_decimal(amount: Decimal) -> None:
    with pytest.raises(ValidationError) as exc:
        Money(amount, "EUR")
    assert exc.value.code == "money.amount.non_finite"


@pytest.mark.parametrize("currency", ["", "EU", "EURO", "€UR", "12A"])
def test_money_rejects_invalid_currency_shape(currency: str) -> None:
    with pytest.raises(ValidationError) as exc:
        Money(Decimal("1"), currency)
    assert exc.value.code == "money.currency.invalid"
