"""Track S AUD-FIX-09: privacy notices and release truth are reviewable."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = (
    "whatsapp-and-referral-crm-analysis.md",
    "alumni-directory-and-network-activation.md",
    "association-member-lifecycle-and-onboarding.md",
    "freelance-mission-hunt-and-kpis.md",
    "public-tenders-and-rfp-bid-management.md",
    "student-internship-alternance-job-hunt.md",
    "web-agency-client-lifecycle.md",
)
SKILLS = (
    "agency-client-lifecycle",
    "alumni-directory-activation",
    "association-member-onboarding",
    "freelance-mission-hunter",
    "public-tender-qualifier",
    "student-career-launch",
    "whatsapp-dialog-processor",
)
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)


@pytest.mark.parametrize("filename", ANALYSIS)
def test_business_blueprint_explains_privacy_boundary(filename: str) -> None:
    source = (ROOT / "docs" / "analysis" / filename).read_text(encoding="utf-8")
    assert "Privacy and implementation notice (Track S / AUD-FIX-09)" in source
    assert "valid processing purpose and lawful basis" in source
    assert "retention/deletion schedule" in source
    assert "ILLUSTRATIVE / NON-EXECUTABLE" in source
    assert "aud-fix-09-privacy-governance.md" in source
    assert all(m.group(1).lower() in {"example.org", "example.com", "example.net"}
               for m in EMAIL_PATTERN.finditer(source))


@pytest.mark.parametrize("slug", SKILLS)
def test_agent_recipe_has_independent_privacy_and_execution_warning(slug: str) -> None:
    source = (ROOT / ".agents" / "skills" / slug / "examples.md").read_text(
        encoding="utf-8"
    )
    assert "AUD-FIX-09: ILLUSTRATIVE RECIPE / NOT VERIFIED FOR EXECUTION" in source
    assert "legal basis" in source
    assert "authorization before any upload" in source
    assert "not provide authentication" in source
    assert all(m.group(1).lower() in {"example.org", "example.com", "example.net"}
               for m in EMAIL_PATTERN.finditer(source))


def test_release_ledger_does_not_claim_unverified_pypi() -> None:
    p = ROOT / "docs" / "development" / "1.3.0" / "aud-fix-09-release-evidence-ledger.md"
    text = p.read_text(encoding="utf-8")
    assert "UNVERIFIED" in text
    assert "NO-GO" in text
    assert "600fddbc29eb2fc0a1ab290e2ea0c03a01791868" in text
    assert "not a byte-level" in text
