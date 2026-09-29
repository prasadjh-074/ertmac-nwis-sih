"""Evidence fusion, provenance, and rationale generation."""

from .fusion import fuse_evidence
from .models import (
    EvidenceGroup,
    FusedEvidence,
    FusedEvidenceItem,
    MissingInfo,
    ProvenanceRecord,
    SourceDifference,
)
from .provenance import build_provenance, collect_source_systems, get_source_type
from .rationale import generate_confidence_basis, generate_rationale

__all__ = [
    "fuse_evidence",
    "build_provenance",
    "collect_source_systems",
    "get_source_type",
    "generate_rationale",
    "generate_confidence_basis",
    "FusedEvidence",
    "FusedEvidenceItem",
    "EvidenceGroup",
    "ProvenanceRecord",
    "SourceDifference",
    "MissingInfo",
]
