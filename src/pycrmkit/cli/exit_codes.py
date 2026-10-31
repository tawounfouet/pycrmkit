"""Stable process exit codes for the PyCRMKit CLI."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes for the CLI v1 specification."""

    SUCCESS = 0  # Nominal execution
    GENERAL_ERROR = 1  # User argument error or generic failure
    VALIDATION_ERROR = 2  # Static validation failure
    EXECUTION_FAILURE = 3  # Runtime execution failure
    SECURITY_ERROR = 4  # Security policy violation
    MISSING_OPTIONAL_DEPENDENCY = 11  # Missing optional extra (cli, postgresql, etc.)
    FILESYSTEM_ERROR = 12  # File not found or permission denied
    INTERNAL_ERROR = 70  # Unhandled internal exception
    INTERRUPTED = 130  # Interrupted by user SIGINT (Ctrl+C)
    BROKEN_PIPE = 141  # Broken pipe SIGPIPE


__all__ = ["ExitCode"]
