"""Entity resolution against the seeded demo reference tables
(ref_wells/ref_licences/ref_fields/ref_companies). Tiered, conservative
matching -- exact -> alias -> fuzzy (high threshold). Anything below
threshold is left UNRESOLVED rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from ingestion.config import get_settings
from ingestion.normalization.name_normalizer import (
    normalize_company_name,
    normalize_licence_name,
    normalize_well_name,
)
from ingestion.storage.models import RefCompany, RefField, RefLicence, RefWell


@dataclass
class ResolvedRef:
    table: str
    id: int
    confidence: float
    method: str  # "exact" | "alias" | "fuzzy"


def _resolve_against(session: Session, model, name_column: str, id_column: str,
                      table_name: str, normalized_name: str) -> ResolvedRef | None:
    threshold = get_settings().fuzzy_match_threshold

    # 1 & 2: exact match (name_normalizer already folds case/whitespace/
    # known-alias variation into a canonical form before we get here, so a
    # single query covers both "exact" and "normalized-exact").
    row = session.query(model).filter(getattr(model, name_column) == normalized_name).first()
    if row is not None:
        return ResolvedRef(table=table_name, id=getattr(row, id_column), confidence=1.0, method="exact")

    # 3: conservative fuzzy match.
    candidates = session.query(model).all()
    if not candidates:
        return None
    names = [getattr(c, name_column) for c in candidates]
    best = process.extractOne(normalized_name, names, scorer=fuzz.ratio)
    if best is not None and best[1] >= threshold:
        matched_name = best[0]
        matched = next(c for c in candidates if getattr(c, name_column) == matched_name)
        return ResolvedRef(
            table=table_name, id=getattr(matched, id_column),
            confidence=best[1] / 100, method="fuzzy",
        )
    return None


def resolve_well(session: Session, raw_name: str) -> ResolvedRef | None:
    return _resolve_against(
        session, RefWell, "well_name", "well_id", "ref_wells",
        normalize_well_name(raw_name),
    )


def resolve_licence(session: Session, raw_name: str) -> ResolvedRef | None:
    return _resolve_against(
        session, RefLicence, "licence_name", "licence_id", "ref_licences",
        normalize_licence_name(raw_name),
    )


def resolve_company(session: Session, raw_name: str) -> ResolvedRef | None:
    # normalize_company_name already does alias-map lookup (step 3), so
    # an exact match here after normalization covers exact + alias tiers.
    return _resolve_against(
        session, RefCompany, "name", "company_id", "ref_companies",
        normalize_company_name(raw_name),
    )


def resolve_field(session: Session, raw_name: str) -> ResolvedRef | None:
    return _resolve_against(
        session, RefField, "name", "field_id", "ref_fields", raw_name.strip().title(),
    )
