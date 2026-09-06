from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.organizations import (
    Organization,
    OrganizationDomain,
    OrganizationId,
    OrganizationStatus,
)

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
ORGANIZATION_ID = OrganizationId(UUID("00000000-0000-4000-8000-000000000101"))


def test_organization_prefers_trading_name_for_derived_display_name() -> None:
    organization = Organization(
        id=ORGANIZATION_ID,
        created_at=NOW,
        updated_at=NOW,
        legal_name="  Example Holdings SAS  ",
        trading_name=" Example CRM ",
        registration_number=" 123 456 789 ",
        source=" Referral ",
    )

    assert organization.legal_name == "Example Holdings SAS"
    assert organization.trading_name == "Example CRM"
    assert organization.display_name == "Example CRM"
    assert organization.registration_number == "123 456 789"
    assert organization.source == "Referral"


def test_organization_requires_legal_name() -> None:
    with pytest.raises(ValidationError, match="legal_name"):
        Organization(
            id=ORGANIZATION_ID,
            created_at=NOW,
            updated_at=NOW,
            legal_name="   ",
        )


def test_organization_rejects_duplicate_and_multiple_primary_domains() -> None:
    with pytest.raises(Exception, match="duplicate domain"):
        Organization(
            id=ORGANIZATION_ID,
            created_at=NOW,
            updated_at=NOW,
            legal_name="Example",
            domains=(OrganizationDomain("example.com"), OrganizationDomain("EXAMPLE.COM")),
        )

    with pytest.raises(ValidationError, match="primary domain"):
        Organization(
            id=ORGANIZATION_ID,
            created_at=NOW,
            updated_at=NOW,
            legal_name="Example",
            domains=(
                OrganizationDomain("example.com", is_primary=True),
                OrganizationDomain("example.org", is_primary=True),
            ),
        )


def test_organization_archive_is_idempotent_and_blocks_updates() -> None:
    organization = Organization(
        id=ORGANIZATION_ID,
        created_at=NOW,
        updated_at=NOW,
        legal_name="Example SAS",
    )
    archived_at = NOW + timedelta(hours=1)

    organization.archive(archived_at)
    organization.archive(archived_at + timedelta(hours=1))

    assert organization.status is OrganizationStatus.ARCHIVED
    assert organization.archived_at == archived_at
    assert organization.updated_at == archived_at
    with pytest.raises(InvalidStateError, match="archived"):
        organization.ensure_mutable()
