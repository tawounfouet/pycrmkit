"""Run external identity contracts against the Django ORM adapter."""

from pycrmkit.integrations.django.repositories import DjangoExternalIdentityRepository
from tests.contracts.external_identities_repository import (
    assert_external_identity_repository_contract,
)


def test_django_external_identity_repository_passes_contract() -> None:
    assert_external_identity_repository_contract(DjangoExternalIdentityRepository())
