# Money

`Money` is the currency-aware monetary primitive introduced by PyCRMKit `0.3.0a1`.

```python
from decimal import Decimal

from pycrmkit.core import Money

price = Money(amount=Decimal("15000"), currency="EUR")
```

## Contract

- `amount` must be an actual `Decimal`; `float`, `int` and string amounts are rejected.
- non-finite Decimal values (`NaN`, `Infinity`) are rejected.
- `currency` is required and normalized to uppercase.
- currency validation is structural: exactly three ASCII letters. PyCRMKit does not bundle an ISO currency registry at this milestone.
- the primitive is immutable.

The strict Decimal rule prevents accidental binary floating-point persistence in future Opportunity/revenue models.
