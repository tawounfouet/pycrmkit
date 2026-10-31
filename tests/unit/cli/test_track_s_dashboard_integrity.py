"""AUD-FIX-07: currency integrity and sampling warnings in CLI dashboard."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from pycrmkit.cli.bootstrap import main
from pycrmkit.cli.commands.dashboard import _display_amounts, _sum_by_currency
from pycrmkit.cli.exit_codes import ExitCode


def test_currency_aggregation_never_adds_eur_to_usd() -> None:
    deals = [
        SimpleNamespace(
            currency="EUR", estimated_value=Decimal("100"), probability=Decimal("0.5")
        ),
        SimpleNamespace(
            currency="USD", estimated_value=Decimal("200"), probability=Decimal("0.25")
        ),
    ]
    assert _sum_by_currency(deals) == {"EUR": Decimal("100"), "USD": Decimal("200")}
    assert _sum_by_currency(deals, weighted=True) == {
        "EUR": Decimal("50"),
        "USD": Decimal("50"),
    }
    display = _display_amounts(_sum_by_currency(deals))
    assert "USD" in display
    assert "€" in display


def test_empty_valuations_are_not_labelled_zero_eur() -> None:
    assert _display_amounts({}) == "N/A (no priced deals)"


def test_demo_dashboard_reports_sample_as_partial(monkeypatch, capsys) -> None:
    from pycrmkit.cli.commands import dashboard

    original = dashboard.query_opportunities

    def mocked_query(crm, query=None, page=None):
        result = original(crm, query=query, page=page)
        if result.total > 0:
            return SimpleNamespace(items=result.items, total=result.total + 150)
        return result

    monkeypatch.setattr(dashboard, "query_opportunities", mocked_query)
    assert main(["dashboard", "--demo"], prog_name="pck") == int(ExitCode.SUCCESS)
    output = capsys.readouterr().out
    assert "PARTIAL RESULTS" in output
    assert "Observed Win Rate" in output
    assert "Real-time Operational Telemetry" not in output
