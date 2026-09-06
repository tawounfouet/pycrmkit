"""Run Audit repository contracts against the official Memory adapter."""

from pycrmkit.audit import AuditRepository
from pycrmkit.storage.memory import MemoryAuditRepository

from ...contracts.audit_repository import assert_audit_repository_contract


def test_memory_audit_repository_contract() -> None:
    repository: AuditRepository = MemoryAuditRepository()
    assert_audit_repository_contract(repository)
