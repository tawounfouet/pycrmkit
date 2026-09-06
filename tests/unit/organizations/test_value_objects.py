import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.organizations import OrganizationAddress, OrganizationDomain, normalize_domain


def test_organization_domain_normalizes_case_trailing_dot_and_idna() -> None:
    domain = OrganizationDomain("  EXAMPLE.COM. ", is_primary=True)

    assert domain.value == "EXAMPLE.COM"
    assert domain.normalized == "example.com"
    assert domain.is_primary is True
    assert normalize_domain("MÜNICH.example") == "xn--mnich-kva.example"


def test_organization_domain_rejects_url_or_single_label() -> None:
    with pytest.raises(ValidationError, match="domain"):
        OrganizationDomain("https://example.com")
    with pytest.raises(ValidationError, match="domain"):
        OrganizationDomain("localhost")


def test_organization_address_normalizes_fields_and_country_code() -> None:
    address = OrganizationAddress(
        line1="  8  avenue des Champs-Élysées ",
        city=" Paris ",
        postal_code="75008",
        country_code="fr",
        is_primary=True,
    )

    assert address.line1 == "8 avenue des Champs-Élysées"
    assert address.city == "Paris"
    assert address.country_code == "FR"
    assert "75008" in address.formatted
