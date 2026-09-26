"""Run webhook delivery repository contract against the Memory adapter."""

from pycrmkit.storage.memory import MemoryWebhookDeliveryRepository

from ...contracts.webhook_deliveries_repository import (
    assert_webhook_delivery_repository_contract,
    make_delivery,
)


def test_memory_webhook_delivery_repository_passes_contract() -> None:
    assert_webhook_delivery_repository_contract(MemoryWebhookDeliveryRepository())


def test_memory_webhook_delivery_repository_isolates_loaded_mutations() -> None:
    repository = MemoryWebhookDeliveryRepository()
    delivery = make_delivery()
    repository.save(delivery)

    loaded = repository.get(delivery.id)
    loaded.last_error_code = "changed-without-save"

    assert repository.get(delivery.id).last_error_code is None
