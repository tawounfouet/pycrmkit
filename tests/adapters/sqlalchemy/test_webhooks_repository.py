"""Run Webhook repository contracts against the SQLAlchemy adapter."""

from sqlalchemy.orm import Session

from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemyWebhookSubscriptionRepository,
)

from ...contracts.webhooks_repository import (
    assert_webhook_subscription_repository_contract,
    make_subscription,
)


def test_sqlalchemy_webhook_repository_passes_contract(session: Session) -> None:
    assert_webhook_subscription_repository_contract(
        SQLAlchemyWebhookSubscriptionRepository(session)
    )


def test_sqlalchemy_webhook_repository_isolates_mutations(
    session: Session,
) -> None:
    repository = SQLAlchemyWebhookSubscriptionRepository(session)
    subscription = make_subscription(
        10,
        url="https://hooks.example.com/isolation",
        events=("contact.created",),
    )
    repository.save(subscription)

    loaded = repository.get(subscription.id)
    loaded.disable(loaded.updated_at)

    assert repository.get(subscription.id).enabled is True
