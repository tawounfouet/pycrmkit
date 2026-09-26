"""Run Webhook repository contracts against the official Memory adapter."""

from pycrmkit.storage.memory import MemoryWebhookSubscriptionRepository

from ...contracts.webhooks_repository import (
    assert_webhook_subscription_repository_contract,
    make_subscription,
)


def test_memory_webhook_repository_passes_contract() -> None:
    assert_webhook_subscription_repository_contract(
        MemoryWebhookSubscriptionRepository()
    )


def test_memory_webhook_repository_isolates_mutations() -> None:
    repository = MemoryWebhookSubscriptionRepository()
    subscription = make_subscription(
        10,
        url="https://hooks.example.com/isolation",
        events=("contact.created",),
    )
    repository.save(subscription)

    loaded = repository.get(subscription.id)
    loaded.disable(loaded.updated_at)

    assert repository.get(subscription.id).enabled is True
