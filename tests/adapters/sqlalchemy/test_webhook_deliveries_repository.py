"""Run webhook delivery repository contract against the SQLAlchemy adapter."""

from sqlalchemy.orm import Session

from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemyWebhookDeliveryRepository,
)

from ...contracts.webhook_deliveries_repository import (
    assert_webhook_delivery_repository_contract,
    make_delivery,
)


def test_sqlalchemy_webhook_delivery_repository_passes_contract(
    session: Session,
) -> None:
    assert_webhook_delivery_repository_contract(
        SQLAlchemyWebhookDeliveryRepository(session)
    )


def test_sqlalchemy_webhook_delivery_repository_isolates_loaded_mutations(
    session: Session,
) -> None:
    repository = SQLAlchemyWebhookDeliveryRepository(session)
    delivery = make_delivery()
    repository.save(delivery)

    loaded = repository.get(delivery.id)
    loaded.last_error_code = "changed-without-save"

    assert repository.get(delivery.id).last_error_code is None
