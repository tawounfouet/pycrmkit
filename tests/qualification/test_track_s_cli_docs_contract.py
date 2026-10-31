"""AUD-FIX-05: prevent unsupported CLI examples being advertised as runnable."""

from __future__ import annotations

import re
from pathlib import Path

from typer.main import get_command

from pycrmkit.cli.app import app

ROOT = Path(__file__).resolve().parents[2]
SKILLS = (
    "agency-client-lifecycle",
    "alumni-directory-activation",
    "association-member-onboarding",
    "freelance-mission-hunter",
    "public-tender-qualifier",
    "student-career-launch",
    "whatsapp-dialog-processor",
)


def test_readme_shell_commands_match_registered_cli() -> None:
    from click import Group

    group = get_command(app)
    assert isinstance(group, Group)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for line in readme.splitlines():
        match = re.match(r"^\s*pck\s+([\w-]+)(?:\s+([\w-]+))?", line)
        if match is None:
            continue
        first, second = match.groups()
        if first.startswith("-"):
            continue
        assert first in group.commands, f"README advertises unknown pck group: {first}"
        subgroup = group.commands[first]
        if second and not second.startswith("-") and isinstance(subgroup, Group):
            assert second in subgroup.commands, f"README has unsupported pck {first} {second}"


def test_agent_skills_are_unambiguously_labelled_as_illustrative() -> None:
    for slug in SKILLS:
        path = ROOT / ".agents" / "skills" / slug / "SKILL.md"
        content = path.read_text(encoding="utf-8")
        assert "ILLUSTRATIVE / NOT EXECUTABLE" in content, str(path)
        assert "linked `workflow.md`" in content, str(path)
        assert "pck --help" in content, str(path)


def test_agent_manifest_does_not_claim_qualified_runtime() -> None:
    content = (ROOT / ".agents" / "AGENTS.md").read_text(encoding="utf-8")
    assert "DOCUMENTATION ONLY" in content
    assert "not provide an autonomous" in content
