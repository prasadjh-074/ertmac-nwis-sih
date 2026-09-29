"""Deterministic entity extraction: regex for structured patterns (well
IDs, licences, formations-with-suffix, depths, dates) plus dictionary/alias
lookups (companies, known formation names) built from ontology/aliases.yaml.

No ML, no fine-tuning, no spaCy model download -- intentionally simple and
explainable for a hackathon demo.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ingestion import ontology
from ingestion.schemas import Entity

WELL_ID_RE = re.compile(r"\b\d{1,2}/\d{1,2}-[A-Z]?\d{1,3}[A-Z]?\b")
LICENCE_RE = re.compile(r"\bPL\s?(\d{1,4}\s?[A-Z]?)\b", re.IGNORECASE)
# A single capitalized word immediately before "Fm"/"Formation" -- NPD-style
# formation names in this domain are single proper nouns (Heimdal, Sleipner,
# ...). Matching more than one preceding word would risk swallowing an
# unrelated capitalized word earlier in the sentence (e.g. "The Heimdal Fm.").
FORMATION_SUFFIX_RE = re.compile(r"\b([A-Z][a-zA-Z]+)\s+(Formation|Fm\.?)\b")
DEPTH_VALUE_RE = re.compile(
    r"\b(\d{1,6}(?:\.\d+)?)\s?(m|ft|meters|feet|km|cm)\b", re.IGNORECASE
)
_MONTHS = (
    "January|February|March|April|May|June|July|August|September|"
    "October|November|December"
)
DATE_RE = re.compile(
    rf"\b(\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}"
    rf"|\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}"
    rf"|(?:{_MONTHS})\s+\d{{1,2}},?\s+\d{{4}})\b"
)
PRODUCTION_RE = re.compile(
    r"\b(\d[\d,]*(?:\.\d+)?)\s?(bbl/d|bbl|barrels|Sm3|boe)\b", re.IGNORECASE
)


def _flatten_alias_map(alias_map: dict[str, list[str]]) -> dict[str, str]:
    """canonical -> [surface forms] becomes {surface_form_lower: canonical}."""
    flat: dict[str, str] = {}
    for canonical, surface_forms in alias_map.items():
        for form in surface_forms:
            flat[form.lower()] = canonical
    return flat


@lru_cache(maxsize=None)
def _company_lookup() -> tuple[re.Pattern, dict[str, str]]:
    companies = {
        k: v for k, v in ontology.aliases()["company"].items() if k != "operator_keywords"
    }
    flat = _flatten_alias_map(companies)
    return _build_alias_pattern(flat), flat


@lru_cache(maxsize=None)
def _formation_lookup() -> tuple[re.Pattern, dict[str, str]]:
    known = ontology.aliases()["formation"]["known"]
    flat = _flatten_alias_map(known)
    return _build_alias_pattern(flat), flat


@lru_cache(maxsize=None)
def _field_lookup() -> tuple[re.Pattern, dict[str, str]]:
    fields = ontology.aliases().get("field", {})
    flat = _flatten_alias_map(fields)
    return _build_alias_pattern(flat), flat


@lru_cache(maxsize=None)
def _log_curve_lookup() -> tuple[re.Pattern, dict[str, str]]:
    curves = ontology.aliases()["log_curve"]
    flat = _flatten_alias_map(curves)
    return _build_alias_pattern(flat), flat


def _build_alias_pattern(flat: dict[str, str]) -> re.Pattern:
    # Longest-first so e.g. "Equinor ASA" matches before the shorter "Equinor".
    forms_sorted = sorted(flat.keys(), key=len, reverse=True)
    escaped = [re.escape(f) for f in forms_sorted]
    pattern = r"\b(" + "|".join(escaped) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


def _extract_by_dictionary(text: str, page: int | None, entity_type: str, source: str,
                            pattern: re.Pattern, flat: dict[str, str], confidence: float) -> list[Entity]:
    entities = []
    for m in pattern.finditer(text):
        canonical = flat.get(m.group(0).lower())
        if canonical is None:
            continue
        entities.append(
            Entity(
                type=entity_type,
                text=m.group(0),
                normalized_value=canonical,
                confidence=confidence,
                page=page,
                start=m.start(),
                end=m.end(),
                source=source,
            )
        )
    return entities


def extract_entities(text: str, page: int | None = None) -> list[Entity]:
    entities: list[Entity] = []

    for m in WELL_ID_RE.finditer(text):
        entities.append(
            Entity(
                type="WELL", text=m.group(0), normalized_value=m.group(0),
                confidence=0.95, page=page, start=m.start(), end=m.end(),
                source="regex:well_id",
            )
        )

    for m in LICENCE_RE.finditer(text):
        normalized = f"PL {m.group(1).strip()}"
        entities.append(
            Entity(
                type="LICENCE", text=m.group(0), normalized_value=normalized,
                confidence=0.9, page=page, start=m.start(), end=m.end(),
                source="regex:licence",
            )
        )

    for m in FORMATION_SUFFIX_RE.finditer(text):
        entities.append(
            Entity(
                type="FORMATION", text=m.group(0), normalized_value=m.group(1),
                confidence=0.85, page=page, start=m.start(), end=m.end(),
                source="regex:formation_suffix",
            )
        )

    for m in DEPTH_VALUE_RE.finditer(text):
        entities.append(
            Entity(
                type="DEPTH", text=m.group(0), normalized_value=m.group(0),
                confidence=0.8, page=page, start=m.start(), end=m.end(),
                source="regex:depth",
            )
        )

    for m in DATE_RE.finditer(text):
        entities.append(
            Entity(
                type="DATE", text=m.group(0), normalized_value=m.group(0),
                confidence=0.75, page=page, start=m.start(), end=m.end(),
                source="regex:date",
            )
        )

    for m in PRODUCTION_RE.finditer(text):
        entities.append(
            Entity(
                type="PRODUCTION", text=m.group(0), normalized_value=m.group(0),
                confidence=0.8, page=page, start=m.start(), end=m.end(),
                source="regex:production",
            )
        )

    company_pattern, company_flat = _company_lookup()
    entities.extend(
        _extract_by_dictionary(
            text, page, "COMPANY", "alias:company", company_pattern, company_flat, 0.9
        )
    )

    field_pattern, field_flat = _field_lookup()
    if field_flat:
        entities.extend(
            _extract_by_dictionary(
                text, page, "FIELD", "alias:field", field_pattern, field_flat, 0.85
            )
        )

    log_curve_pattern, log_curve_flat = _log_curve_lookup()
    entities.extend(
        _extract_by_dictionary(
            text, page, "LOG_CURVE", "alias:log_curve", log_curve_pattern,
            log_curve_flat, 0.85,
        )
    )

    formation_pattern, formation_flat = _formation_lookup()
    existing_spans = {(e.start, e.end) for e in entities if e.type == "FORMATION"}
    for m in formation_pattern.finditer(text):
        # Skip if this span (or an overlapping one) was already captured by
        # FORMATION_SUFFIX_RE above -- avoid duplicate FORMATION entities for
        # e.g. "Heimdal Fm" (both patterns would otherwise match "Heimdal").
        if any(m.start() < end and start < m.end() for start, end in existing_spans):
            continue
        canonical = formation_flat.get(m.group(0).lower())
        entities.append(
            Entity(
                type="FORMATION", text=m.group(0), normalized_value=canonical,
                confidence=0.7, page=page, start=m.start(), end=m.end(),
                source="alias:formation",
            )
        )

    entities.sort(key=lambda e: e.start)
    return entities
