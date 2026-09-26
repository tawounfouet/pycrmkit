"""Run external identity contracts against the Memory adapter."""

from pycrmkit.storage.memory import MemoryExternalIdentityRepository
from tests.contracts.external_identities_repository import (
    assert_external_identity_repository_contract,
)


def test_memory_external_identity_repository_passes_contract() -> None:
    assert_external_identity_repository_contract(MemoryExternalIdentityRepository())
