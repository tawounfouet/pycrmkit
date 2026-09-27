"""V0.9 deduplication signal extraction and matching."""

from __future__ import annotations

from pycrmkit.dedup import DedupProfile, DedupSignal, StandardSignalMatcher


def test_profile_normalizes_all_documented_dedup_signals() -> None:
    profile = DedupProfile.from_mapping(
        {
            "email": " Ada@Example.COM ",
            "phone": "+33 (6) 12 34 56 78",
            "first_name": " Ada ",
            "last_name": " LOVELACE ",
            "organization": " Analytical Engines ",
            "address": {
                "line1": " 10 Rue des Mathématiques ",
                "postal_code": "75001",
                "city": " Paris ",
                "country_code": "FR",
            },
            "external_identity": {
                "system": "HubSpot",
                "external_id": "  Contact-42  ",
            },
            "custom_identifiers": {
                "customer_number": "  C-001  ",
            },
        }
    )

    assert profile.emails == frozenset({"ada@example.com"})
    assert profile.phones == frozenset({"+33612345678"})
    assert profile.full_name == "ada lovelace"
    assert profile.organization == "analytical engines"
    assert profile.addresses == frozenset(
        {"10 rue des mathématiques|75001|paris|fr"}
    )
    assert profile.external_identities == frozenset(
        {("hubspot", "Contact-42")}
    )
    assert profile.custom_identifiers == frozenset(
        {("customer_number", "C-001")}
    )


def test_standard_matcher_reports_every_supported_signal() -> None:
    incoming = DedupProfile.from_mapping(
        {
            "email": "ada@example.com",
            "phone": "+33612345678",
            "full_name": "Ada Lovelace",
            "organization": "Analytical Engines",
            "address": "10 Rue des Mathématiques, Paris",
            "external_identity": {"system": "hubspot", "external_id": "42"},
            "custom_identifiers": {"customer_number": "C-001"},
        }
    )
    candidate = DedupProfile.from_mapping(
        {
            "email": "ADA@EXAMPLE.COM",
            "phone": "+33 6 12 34 56 78",
            "display_name": "ADA LOVELACE",
            "company": "ANALYTICAL ENGINES",
            "address": "10 rue des mathématiques, paris",
            "external_identities": (
                {"system": "HubSpot", "external_id": "42"},
            ),
            "custom_identifiers": {"customer_number": "C-001"},
        }
    )

    matches = StandardSignalMatcher().match(incoming, candidate)

    assert {match.signal for match in matches} == set(DedupSignal)
