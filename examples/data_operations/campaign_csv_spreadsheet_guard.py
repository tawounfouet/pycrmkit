"""Consumer-side, fail-closed check before opening Campaign CSV in a spreadsheet.

This example deliberately does not mutate the canonical machine-readable CSV.
It is not a guarantee across every spreadsheet application/import mode.
"""
from __future__ import annotations

import csv
import unicodedata
from typing import TextIO


def validate_campaign_csv_for_spreadsheet(source: TextIO) -> int:
    """Reject candidate formula cells; import validated columns as TEXT."""
    reader = csv.DictReader(source)
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("Campaign CSV missing/duplicate header")
    count = 0
    for number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"Campaign CSV extra columns on row {number}")
        for field, value in row.items():
            if value is None:
                raise ValueError(f"Campaign CSV missing field {field} on row {number}")
            cell = unicodedata.normalize("NFKC", value).lstrip()
            if cell.startswith(("=", "+", "-", "@")):
                raise ValueError(
                    f"Campaign CSV spreadsheet formula risk at row {number}, field {field}"
                )
        count += 1
    return count
