"""Deterministic unit normalization: length -> meters, date -> ISO 8601.
Never raises on bad input from document text -- callers get None/ValueError
that they turn into a WARNING validation result rather than a crash.
"""
from __future__ import annotations

import re
from datetime import datetime

from ingestion import ontology

_LENGTH_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s?(km|kilometers?|cm|centimeters?|ft|feet|foot|m|meters?)\b",
    re.IGNORECASE,
)


def normalize_length(value: float, unit: str) -> float:
    """Convert a (value, unit) pair to meters. Raises ValueError for an
    unrecognized unit -- callers must catch this and record a WARNING
    rather than let it propagate.
    """
    conversions = ontology.units()["length"]["conversions"]
    factor = conversions.get(unit.lower())
    if factor is None:
        raise ValueError(f"Unknown length unit: {unit!r}")
    return round(value * factor, 3)


def parse_length(raw: str) -> float | None:
    """Parse a free-text length like '2.89 km' or '2890 m' and return the
    value in meters, or None if it couldn't be parsed/converted.
    """
    match = _LENGTH_RE.search(raw)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    try:
        return normalize_length(value, unit)
    except ValueError:
        return None


def parse_date(raw: str) -> str | None:
    """Try each configured date format and return ISO 'YYYY-MM-DD' on the
    first match, or None if no format matches (never raises).
    """
    formats = ontology.units()["date_formats"]
    text = raw.strip()
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None
