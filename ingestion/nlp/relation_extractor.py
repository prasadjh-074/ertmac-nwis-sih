"""Deterministic relation extraction over already-extracted entities. No
ML, no autonomous ontology discovery -- fixed relation types (see
ontology/relationships.yaml) via simple proximity + keyword rules.

Two extraction scopes are used, deliberately kept simple:

1. Document/page level, WELL-centric: well reports in this domain
   typically describe attributes of a *single* well as label/value lines
   spread across a page (e.g. "WELL: 30/6-1", "LICENCE: PL 123",
   "OPERATOR: Equinor" each on their own line). When exactly one WELL
   entity is present, it is linked to every LICENCE/COMPANY/FORMATION
   entity found anywhere in the same text -- a conservative, deterministic
   stand-in for full coreference resolution. When zero or multiple wells
   are present, this scope is skipped (too ambiguous to guess).

2. Line level: FORMATION -> DEPTH pairing (HAS_TOP_DEPTH/HAS_BASE_DEPTH),
   since formation-tops tables are inherently line/row-scoped regardless
   of how many wells are on the page.
"""
from __future__ import annotations

import re

from ingestion.schemas import Entity, Relation

_OPERATED_BY_RE = re.compile(r"\boperat(?:ed|or|ing)\b", re.IGNORECASE)
_LOCATED_IN_RE = re.compile(r"\bin the ([A-Z][a-zA-Z]+)\s+field\b", re.IGNORECASE)
_TOP_KEYWORD_RE = re.compile(r"\btop\b", re.IGNORECASE)
_BASE_KEYWORD_RE = re.compile(r"\bbase\b", re.IGNORECASE)
_PRODUCTION_KEYWORD_RE = re.compile(r"\bproduc(?:ed|tion)\b", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def _sentence_spans(line: str) -> list[tuple[int, int]]:
    spans = []
    start = 0
    for m in _SENTENCE_END_RE.finditer(line):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(line)))
    return [s for s in spans if s[1] > s[0]]


def _segments_with_offsets(text: str) -> list[tuple[int, int, str]]:
    """Split text into line-then-sentence segments, each with absolute
    character offsets into `text`.
    """
    segments = []
    pos = 0
    for line in text.split("\n"):
        for sent_start, sent_end in _sentence_spans(line):
            segments.append((pos + sent_start, pos + sent_end, line[sent_start:sent_end]))
        pos += len(line) + 1  # +1 for the split "\n"
    return segments


def _mk_relation(rel_type: str, subject: Entity, obj: Entity, page: int | None,
                  confidence: float, source: str) -> Relation:
    return Relation(type=rel_type, subject=subject, object=obj, confidence=confidence,
                     page=page, source=source)


def extract_relations(text: str, entities: list[Entity], page: int | None = None) -> list[Relation]:
    relations: list[Relation] = []

    wells = [e for e in entities if e.type == "WELL"]
    licences = [e for e in entities if e.type == "LICENCE"]
    companies = [e for e in entities if e.type == "COMPANY"]
    formations = [e for e in entities if e.type == "FORMATION"]
    fields = [e for e in entities if e.type == "FIELD"]
    productions = [e for e in entities if e.type == "PRODUCTION"]

    if len(wells) == 1:
        well = wells[0]
        for lic in licences:
            relations.append(_mk_relation("HAS_LICENCE", well, lic, page, 0.7, "document:single_well"))
        for f in formations:
            relations.append(_mk_relation("HAS_FORMATION", well, f, page, 0.7, "document:single_well"))
        for c in companies:
            relations.append(_mk_relation("OPERATED_BY", well, c, page, 0.65, "document:single_well"))
        for fld in fields:
            relations.append(_mk_relation("LOCATED_IN", well, fld, page, 0.65, "document:single_well"))
        for p in productions:
            relations.append(_mk_relation("HAS_PRODUCTION", well, p, page, 0.6, "document:single_well"))
    else:
        # Ambiguous well count -- fall back to precise same-segment
        # co-occurrence with keyword triggers instead of guessing which
        # well an attribute belongs to.
        for seg_start, seg_end, seg_text in _segments_with_offsets(text):
            seg_entities = [e for e in entities if seg_start <= e.start < seg_end]
            seg_wells = [e for e in seg_entities if e.type == "WELL"]
            seg_licences = [e for e in seg_entities if e.type == "LICENCE"]
            seg_companies = [e for e in seg_entities if e.type == "COMPANY"]
            seg_formations = [e for e in seg_entities if e.type == "FORMATION"]
            seg_fields = [e for e in seg_entities if e.type == "FIELD"]
            seg_productions = [e for e in seg_entities if e.type == "PRODUCTION"]

            for w in seg_wells:
                for lic in seg_licences:
                    relations.append(_mk_relation("HAS_LICENCE", w, lic, page, 0.7, "line:cooccurrence"))
                for f in seg_formations:
                    relations.append(_mk_relation("HAS_FORMATION", w, f, page, 0.7, "line:cooccurrence"))
                if _OPERATED_BY_RE.search(seg_text):
                    for c in seg_companies:
                        relations.append(_mk_relation("OPERATED_BY", w, c, page, 0.75, "line:keyword_operated_by"))
                if _LOCATED_IN_RE.search(seg_text):
                    for fld in seg_fields:
                        relations.append(_mk_relation("LOCATED_IN", w, fld, page, 0.75, "line:keyword_located_in"))
                if _PRODUCTION_KEYWORD_RE.search(seg_text):
                    for p in seg_productions:
                        relations.append(_mk_relation("HAS_PRODUCTION", w, p, page, 0.7, "line:keyword_production"))

    # Line-level FORMATION -> DEPTH pairing (independent of well count).
    for seg_start, seg_end, seg_text in _segments_with_offsets(text):
        seg_entities = sorted(
            [e for e in entities if seg_start <= e.start < seg_end], key=lambda e: e.start
        )
        seg_formations = [e for e in seg_entities if e.type == "FORMATION"]
        seg_depths = [e for e in seg_entities if e.type == "DEPTH"]
        if not seg_formations or not seg_depths:
            continue

        has_top_kw = bool(_TOP_KEYWORD_RE.search(seg_text))
        has_base_kw = bool(_BASE_KEYWORD_RE.search(seg_text))

        for f in seg_formations:
            if has_top_kw and not has_base_kw:
                relations.append(_mk_relation("HAS_TOP_DEPTH", f, seg_depths[0], page, 0.65, "line:keyword_top"))
            elif has_base_kw and not has_top_kw:
                relations.append(_mk_relation("HAS_BASE_DEPTH", f, seg_depths[-1], page, 0.65, "line:keyword_base"))
            elif len(seg_depths) >= 2:
                # No unambiguous keyword (e.g. a plain formation-tops table
                # row "Heimdal   2450 m   2520 m") -- assume table-order
                # convention: first depth is top, second is base.
                relations.append(_mk_relation("HAS_TOP_DEPTH", f, seg_depths[0], page, 0.6, "line:table_order"))
                relations.append(_mk_relation("HAS_BASE_DEPTH", f, seg_depths[1], page, 0.6, "line:table_order"))
            elif len(seg_depths) == 1:
                relations.append(_mk_relation("HAS_TOP_DEPTH", f, seg_depths[0], page, 0.55, "line:single_depth"))

    return relations
