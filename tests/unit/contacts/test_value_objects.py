import pytest

from pycrmkit.contacts import Address, ContactEmail, ContactPhone, VerificationState, normalize_phone
from pycrmkit.exceptions import ValidationError


def test_contact_email_normalizes_and_preserves_primary_state() -> None:
    email = ContactEmail(
        "  Thomas.Example@EXAMPLE.COM  ",
        is_primary=True,
        verification=VerificationState.VERIFIED,
    )
    assert email.value == "Thomas.Example@EXAMPLE.COM"
    assert email.normalized == "thomas.example@example.com"
    assert email.is_primary is True
    assert email.verification is VerificationState.VERIFIED


def test_contact_email_rejects_invalid_shape() -> None:
    with pytest.raises(ValidationError, match="email"):
        ContactEmail("not-an-email")


def test_contact_phone_normalizes_without_country_inference() -> None:
    international = ContactPhone(" +33 (6) 12-34-56-78 ")
    national = ContactPhone("06 12 34 56 78")
    assert international.normalized == "+33612345678"
    assert national.normalized == "0612345678"
    assert normalize_phone("01.44.55.66.77") == "0144556677"


def test_contact_phone_rejects_letters() -> None:
    with pytest.raises(ValidationError, match="phone"):
        ContactPhone("+33 CALL ME")


def test_address_normalizes_fields_and_country_code() -> None:
    address = Address(
        line1="  27  rue du Faubourg  du Temple ",
        city=" Paris ",
        postal_code="75010",
        country_code="fr",
        is_primary=True,
    )
    assert address.line1 == "27 rue du Faubourg du Temple"
    assert address.city == "Paris"
    assert address.country_code == "FR"
    assert "75010" in address.formatted
