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
    group = get_command(app)
    commands = getattr(group, "commands", None)
    assert isinstance(commands, dict)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for line in readme.splitlines():
        match = re.match(r"^\s*pck\s+([\w-]+)(?:\s+([\w-]+))?", line)
        if match is None:
            continue
        first, second = match.groups()
        if first.startswith("-"):
            continue
        assert first in commands, f"README advertises unknown pck group: {first}"
        subgroup = commands[first]
        subcommands = getattr(subgroup, "commands", None)
        if second and not second.startswith("-") and isinstance(subcommands, dict):
            assert second in subcommands, f"README has unsupported pck {first} {second}"


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
    assert "do **not** provide an autonomous" in content
