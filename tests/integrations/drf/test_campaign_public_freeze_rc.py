"""Run 1.2 Campaign DRF field freeze with a configured Django test environment.

The parent conftest configures settings before importing DRF. This is a
source-only optional-extra check; it is not run in core-only wheel smoke.
"""

from __future__ import annotations

import json
from pathlib import Path

from pycrmkit.integrations.django.drf import campaign_serializers

MANIFEST = Path(__file__).parents[2] / "compatibility/public_api_v1_2_campaign_candidate.json"


def test_campaign_drf_declared_fields_match_1_2_candidate() -> None:
    golden = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name, expected in golden["drf_serializer_fields"].items():
        actual = list(getattr(campaign_serializers, name)._declared_fields)
        assert actual == expected, (name, actual, expected)
