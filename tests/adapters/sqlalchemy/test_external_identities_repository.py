"""Run external identity contracts against the SQLAlchemy adapter."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from pycrmkit.contacts import ContactId
from pycrmkit.external_identities import ExternalIdentity, ExternalIdentityId
from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemyExternalIdentityRepository,
)
from tests.contracts.external_identities_repository import (
    assert_external_identity_repository_contract,
)


def test_sqlalchemy_external_identity_repository_passes_contract(
    session: Session,
) -> None:
    assert_external_identity_repository_contract(
        SQLAlchemyExternalIdentityRepository(session)
    )


def test_sqlalchemy_external_identity_restores_typed_contact_owner(
    session: Session,
) -> None:
    repository = SQLAlchemyExternalIdentityRepository(session)
    contact_id = ContactId(UUID("00000000-0000-4000-8000-00000000e101"))
    identity = ExternalIdentity(
        id=ExternalIdentityId(
            UUID("00000000-0000-4000-8000-00000000e102")
        ),
        created_at=datetime(2026, 9, 27, 16, 30, tzinfo=UTC),
        updated_at=datetime(2026, 9, 27, 16, 30, tzinfo=UTC),
        system="legacy_crm",
        external_id="typed-owner",
        entity_type="contact",
        entity_id=contact_id,
    )

    repository.save(identity)
    session.commit()
    session.expire_all()

    reloaded = repository.find("legacy_crm", "typed-owner")

    assert reloaded is not None
    assert reloaded.entity_id == contact_id
    assert isinstance(reloaded.entity_id, ContactId)
    assert reloaded.entity == identity.entity
