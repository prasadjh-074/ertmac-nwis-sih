"""Typed models for the evidence fusion layer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProvenanceRecord(BaseModel):
    """Normalized provenance for one piece of evidence."""

    source_system: str
    retrieval_mechanism: str
    entity_type: str
    dataset: Optional[str] = None
    source_id: Optional[str] = None


class FusedEvidenceItem(BaseModel):
    """One piece of evidence after fusion, with provenance and explanation."""

    evidence_id: str
    source_system: str
    source_type: str
    entity_type: str
    well_id: Optional[str] = None
    source_id: Optional[str] = None
    field: Optional[str] = None
    value: Optional[Any] = None
    relevance: Optional[str] = None
    similarity: Optional[float] = None
    provenance: ProvenanceRecord
    explanation: Optional[str] = None


class SourceDifference(BaseModel):
    """Represents a disagreement between two sources without resolving it."""

    difference_type: str
    field_name: str
    source_a: str
    value_a: Any
    source_b: str
    value_b: Any


class MissingInfo(BaseModel):
    """Explicitly represents information that was unavailable."""

    info_type: str
    description: str
    reason: str


class EvidenceGroup(BaseModel):
    """Evidence grouped by entity (e.g. all evidence about one well)."""

    group_key: str
    entity_type: str
    items: List[FusedEvidenceItem] = Field(default_factory=list)
    source_systems: List[str] = Field(default_factory=list)


class FusedEvidence(BaseModel):
    """Complete output of the evidence fusion step."""

    items: List[FusedEvidenceItem] = Field(default_factory=list)
    groups: List[EvidenceGroup] = Field(default_factory=list)
    differences: List[SourceDifference] = Field(default_factory=list)
    missing: List[MissingInfo] = Field(default_factory=list)
    source_systems: List[str] = Field(default_factory=list)
    item_count: int = 0
