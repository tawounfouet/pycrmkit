"""Run Audit repository contracts against the SQLAlchemy adapter."""

from sqlalchemy.orm import Session

from pycrmkit.audit import AuditRepository
from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyAuditRepository

from ...contracts.audit_repository import assert_audit_repository_contract


def test_sqlalchemy_audit_repository_contract(session: Session) -> None:
    repository: AuditRepository = SQLAlchemyAuditRepository(session)
    assert_audit_repository_contract(repository)
