"""AuditEntry validation and immutability."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.audit import AuditEntry, AuditEntryId
from pycrmkit.exceptions import ValidationError


def test_audit_entry_normalizes_fields_and_freezes_changes() -> None:
    entry = AuditEntry(
        id=AuditEntryId(UUID(int=1)),
        actor_id=" user_1 ",
        action=" Contact.Email_Changed ",
        entity_type=" Contact ",
        entity_id=" 123 ",
        occurred_at=datetime(2026, 9, 6, 18, 0, tzinfo=UTC),
        changes={"email": {"from": "old@example.com", "to": "new@example.com"}},
        correlation_id=" corr-1 ",
    )
    assert entry.action == "contact.email_changed"
    assert entry.entity_type == "contact"
    assert entry.actor_id == "user_1"
    assert entry.correlation_id == "corr-1"
    nested = entry.changes["email"]
    with pytest.raises(TypeError):
        nested["to"] = "mutated"  # type: ignore[index]


def test_audit_action_requires_dotted_identifier() -> None:
    with pytest.raises(ValidationError):
        AuditEntry(
            id=AuditEntryId(UUID(int=1)),
            actor_id=None,
            action="updated",
            entity_type="contact",
            entity_id="1",
            occurred_at=datetime.now(UTC),
        )
