"""Provenance construction for evidence items."""

from __future__ import annotations

from typing import List, Optional

from graph.state import EvidenceItem

from .models import ProvenanceRecord


_RETRIEVAL_MECHANISMS = {
    "well": "vector_similarity",
    "window": "vector_similarity",
    "similarity_score": "vector_similarity",
    "well_info": "sodir_relational",
    "formation": "sodir_relational",
    "field": "sodir_relational",
    "company": "sodir_relational",
    "discovery": "sodir_relational",
    "licence": "sodir_relational",
    "formations": "sodir_relational",
    "stratigraphy": "sodir_relational",
    "well_history": "sodir_relational",
    "casing": "sodir_relational",
    "dst": "sodir_relational",
    "mud": "sodir_relational",
    "core": "sodir_relational",
    "cuttings": "sodir_relational",
    "logs": "sodir_relational",
    # 384-dim sentence-transformer space - never conflated with the
    # 30-dim well/window "vector_similarity" mechanism above.
    "document_chunk": "document_vector_similarity",
}

_SOURCE_TYPES = {
    "well": "vector_similarity",
    "window": "vector_similarity",
    "similarity_score": "computed_metric",
    "well_info": "wellbore_record",
    "formation": "formation_top",
    "field": "field_record",
    "company": "company_record",
    "discovery": "discovery_record",
    "licence": "licence_record",
    "document_chunk": "document",
}


def build_provenance(evidence: EvidenceItem) -> ProvenanceRecord:
    mechanism = _RETRIEVAL_MECHANISMS.get(evidence.entity_type, "unknown")
    return ProvenanceRecord(
        source_system=evidence.source_system,
        retrieval_mechanism=mechanism,
        entity_type=evidence.entity_type,
        dataset=evidence.source_system if evidence.source_system in ("FORCE_2020", "VOLVE") else None,
        source_id=evidence.source_id,
    )


def get_source_type(entity_type: str) -> str:
    return _SOURCE_TYPES.get(entity_type, entity_type)


def collect_source_systems(items: List[EvidenceItem]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item.source_system not in seen:
            seen.add(item.source_system)
            result.append(item.source_system)
    return result
