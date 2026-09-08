"""Decimal-safe money primitive."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from pycrmkit.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Money:
    """Immutable monetary amount with an explicit three-letter currency code.

    The primitive is deliberately strict: callers must provide ``Decimal``.
    Currency validation is structural (three ASCII letters), not a bundled ISO
    currency registry.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if type(self.amount) is not Decimal:
            raise ValidationError(
                "money amount must be a Decimal",
                code="money.amount.decimal_required",
            )
        if not self.amount.is_finite():
            raise ValidationError(
                "money amount must be finite",
                code="money.amount.non_finite",
            )
        currency = unicodedata.normalize("NFKC", self.currency).strip().upper()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise ValidationError(
                "currency must be a three-letter code",
                code="money.currency.invalid",
            )
        object.__setattr__(self, "currency", currency)
