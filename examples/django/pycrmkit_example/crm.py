"""Application-owned PyCRMKit facade wiring for the Django reference app."""

from __future__ import annotations

from typing import cast

from pycrmkit import CRM
from pycrmkit.config import CRMConfig
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import InProcessEventBus
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge

_EVENT_BUS = InProcessEventBus()


def _uow_factory() -> UnitOfWork:
    # The 0.8.x Django bridge intentionally implements only the repositories
    # currently exposed by the reference DRF surface. The cast is confined to
    # application wiring; PyCRMKit's domain UnitOfWork protocol is unchanged.
    return cast(
        UnitOfWork,
        DjangoTransactionBridge(event_publisher=_EVENT_BUS),
    )


_CRM = CRM(
    uow_factory=_uow_factory,
    event_bus=_EVENT_BUS,
    config=CRMConfig(
        events_enabled=True,
        audit_enabled=False,
    ),
    webhook_auto_delivery=False,
)


def get_crm() -> CRM:
    """Return the application-owned facade used by DRF dependencies."""

    return _CRM
