"""Deterministic name normalization: formation/company/well name casing and
suffix handling. Always preserves the caller's raw value -- these functions
return a new normalized string, they never mutate the source Entity.
"""
from __future__ import annotations

import re

from ingestion import ontology

_FORMATION_SUFFIX_RE = re.compile(r"\s*(Formation|Fm\.?)\s*$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_formation_name(raw: str) -> str:
    """'HEIMDAL FM' / 'Heimdal Fm.' / 'Heimdal Formation' -> 'Heimdal'."""
    stripped = _FORMATION_SUFFIX_RE.sub("", raw).strip()
    return stripped.title()


def normalize_well_name(raw: str) -> str:
    """'30 / 6-1' -> '30/6-1' (well IDs are already canonical once matched
    by entity_extractor's regex; this mainly fixes stray whitespace).
    """
    collapsed = _WHITESPACE_RE.sub("", raw.strip())
    return collapsed


def normalize_company_name(raw: str) -> str:
    """Alias-map lookup against ontology/aliases.yaml; falls back to
    title-casing when no alias is known (still surfaced as lower-confidence
    downstream since it wasn't a dictionary hit).
    """
    companies = {
        k: v for k, v in ontology.aliases()["company"].items() if k != "operator_keywords"
    }
    raw_lower = raw.strip().lower()
    for canonical, forms in companies.items():
        if raw_lower in {f.lower() for f in forms}:
            return canonical
    return raw.strip().title()


def normalize_licence_name(raw: str) -> str:
    """'PL123' / 'pl 123' / 'PL 123A' -> 'PL 123' (or 'PL 123A')."""
    match = re.match(r"PL\s?(\d+\s?[A-Za-z]?)", raw.strip(), re.IGNORECASE)
    if not match:
        return raw.strip()
    return f"PL {match.group(1).strip().upper()}"
