from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pycrmkit.contacts import ContactId
from pycrmkit.core.time import FixedClock
from pycrmkit.opportunities import OpportunityQuery, OpportunityService, OpportunityStatus
from pycrmkit.storage.memory import MemoryOpportunityRepository

NOW = datetime(2026, 9, 9, 9, 0, tzinfo=UTC)


def test_service_creates_and_lists_opportunity() -> None:
    repository = MemoryOpportunityRepository()
    service = OpportunityService(repository, clock=FixedClock(NOW))
    opportunity = service.create(
        name="Enterprise renewal",
        contact_id=ContactId(UUID(int=10)),
        estimated_value=Decimal("12000"),
        currency="EUR",
        probability=Decimal("0.5"),
        expected_close_date=date(2026, 11, 1),
    )
    page = service.list(OpportunityQuery(status="open"))
    assert page.items == (opportunity,)


def test_service_persists_won_lost_and_cancelled_lifecycle() -> None:
    clock = FixedClock(NOW)
    repository = MemoryOpportunityRepository()
    service = OpportunityService(repository, clock=clock)

    won = service.create(name="Won", contact_id=ContactId(UUID(int=10)))
    lost = service.create(name="Lost", contact_id=ContactId(UUID(int=10)))
    cancelled = service.create(name="Cancelled", contact_id=ContactId(UUID(int=10)))

    clock.advance(timedelta(minutes=1))
    assert service.mark_won(won.id).status is OpportunityStatus.WON
    assert service.mark_lost(lost.id).status is OpportunityStatus.LOST
    assert service.cancel(cancelled.id).status is OpportunityStatus.CANCELLED
