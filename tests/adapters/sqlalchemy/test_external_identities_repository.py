"""Run external identity contracts against the SQLAlchemy adapter."""

from sqlalchemy.orm import Session

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
