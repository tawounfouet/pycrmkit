"""Unified Rich console instance for PyCRMKit CLI."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "danger": "bold red",
        "success": "bold green",
        "primary": "bold blue",
        "muted": "dim white",
    }
)

console = Console(theme=custom_theme)
error_console = Console(theme=custom_theme, stderr=True)

__all__ = ["console", "error_console", "custom_theme"]
