"""Deterministic rationale generation."""

from __future__ import annotations

from typing import List, Optional

from .models import FusedEvidence, MissingInfo


_INTENT_RATIONALE = {
    "similar_wells": "Matched using cosine similarity between the query well embedding and candidate well embeddings.",
    "similar_windows": "Matched using cosine similarity between the query depth-window embedding and candidate window embeddings.",
    "well_information": "Information retrieved from the SODIR wellbore and related entities via the identity link.",
    "formation_information": "Formation tops retrieved from SODIR formation_top records linked to the wellbore.",
    "compare_wells": "Side-by-side comparison of two wells using SODIR metadata and embedding cosine similarity.",
    "geological_context": "Context combines SODIR relational evidence with available well/retrieval evidence.",
    "document_search": "Matched using cosine similarity between the query text embedding and document "
                        "chunk embeddings (a separate 384-dim vector space from the 30-dim well/window embeddings).",
}


def generate_rationale(
    intent: Optional[str],
    fused: FusedEvidence,
) -> List[str]:
    lines: List[str] = []

    if intent and intent in _INTENT_RATIONALE:
        lines.append(_INTENT_RATIONALE[intent])

    if fused.item_count > 0:
        lines.append(f"{fused.item_count} evidence item(s) collected.")

    vector_items = [i for i in fused.items if i.source_type == "vector_similarity"]
    sodir_items = [i for i in fused.items if i.provenance.retrieval_mechanism == "sodir_relational"]
    document_items = [i for i in fused.items if i.source_type == "document"]

    if vector_items:
        sims = [i.similarity for i in vector_items if i.similarity is not None]
        if sims:
            lines.append(f"Vector similarity evidence: {len(vector_items)} item(s), "
                         f"similarity range [{min(sims):.3f}, {max(sims):.3f}].")
        else:
            lines.append(f"Vector similarity evidence: {len(vector_items)} item(s).")

    if sodir_items:
        lines.append(f"SODIR relational evidence: {len(sodir_items)} item(s).")

    if document_items:
        sims = [i.similarity for i in document_items if i.similarity is not None]
        if sims:
            lines.append(f"Document evidence: {len(document_items)} chunk(s), "
                         f"similarity range [{min(sims):.3f}, {max(sims):.3f}] "
                         f"(separate 384-dim document vector space).")
        else:
            lines.append(f"Document evidence: {len(document_items)} chunk(s).")

    if len(fused.source_systems) >= 2:
        lines.append(f"Provenance spans {len(fused.source_systems)} source system(s): "
                     f"{', '.join(fused.source_systems)}.")
    elif len(fused.source_systems) == 1:
        lines.append(f"Provenance from single source: {fused.source_systems[0]}.")

    if fused.differences:
        lines.append(f"{len(fused.differences)} source difference(s) detected and preserved.")

    for m in fused.missing:
        lines.append(f"Missing: {m.description} ({m.reason}).")

    return lines


def generate_confidence_basis(
    factors: dict,
    fused: FusedEvidence,
) -> List[str]:
    basis: List[str] = []

    status = factors.get("status_component", 0.0)
    if status >= 1.0:
        basis.append("query resolved successfully")
    elif status >= 0.5:
        basis.append("query partially resolved")
    else:
        basis.append("query resolution failed or returned no data")

    count = factors.get("result_count", 0)
    if count > 0:
        basis.append(f"{count} retrieval result(s) found")
    else:
        basis.append("no retrieval results found")

    sources = factors.get("sources", [])
    if len(sources) >= 2:
        basis.append(f"provenance from {len(sources)} source(s)")
    elif len(sources) == 1:
        basis.append(f"provenance from single source ({sources[0]})")
    else:
        basis.append("no provenance available")

    sim = factors.get("similarity_component", 0.0)
    if sim > 0.5:
        basis.append("high similarity evidence available")
    elif sim == 0.5:
        basis.append("similarity not applicable for this intent")
    elif sim > 0.0:
        basis.append("moderate similarity evidence")
    else:
        basis.append("no similarity evidence available")

    return basis
