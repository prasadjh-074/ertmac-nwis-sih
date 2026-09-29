"""Canonical drilling event model.

Every event retains full source provenance.  Fields that are
unavailable remain None — never fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    MUD_LOSS = "mud_loss"
    STUCK_PIPE = "stuck_pipe"
    KICK = "kick"
    OVERPRESSURE = "overpressure"
    TORQUE_SPIKE = "torque_spike"
    CEMENTING_ISSUE = "cementing_issue"
    CASING_ISSUE = "casing_issue"
    FISHING = "fishing"
    NPT = "npt"
    OTHER = "other"


class EventSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class EventProvenance:
    """Where this event was extracted from."""

    source_type: str
    source_table: Optional[str] = None
    source_record_id: Optional[int] = None
    source_document_id: Optional[str] = None
    source_chunk_id: Optional[str] = None
    source_file_name: Optional[str] = None
    extraction_method: str = "unknown"
    extraction_confidence: float = 0.0
    raw_text_snippet: Optional[str] = None


@dataclass
class DrillingEvent:
    """A single canonical drilling event extracted from historical data.

    Every event carries its source provenance so it can be traced back
    to the original record.  Uncertain events carry low
    extraction_confidence in their provenance.
    """

    event_id: Optional[int] = None
    well_id: str = ""
    dataset: str = ""
    event_type: EventType = EventType.OTHER
    subtype: Optional[str] = None
    depth_start_m: Optional[float] = None
    depth_end_m: Optional[float] = None
    formation: Optional[str] = None
    severity: EventSeverity = EventSeverity.UNKNOWN
    description: str = ""
    indicators: List[str] = field(default_factory=list)
    mitigation: Optional[str] = None
    outcome: Optional[str] = None
    provenance: EventProvenance = field(
        default_factory=lambda: EventProvenance(source_type="unknown")
    )
    sodir_wellbore_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorrelatedEvent:
    """A historical event enriched with correlation factors to a
    current well/depth/formation context."""

    event: DrillingEvent
    source_well_id: str
    source_dataset: str
    distance_km: Optional[float] = None
    geological_similarity: Optional[float] = None
    depth_overlap: bool = False
    depth_difference_m: Optional[float] = None
    formation_match: bool = False
    relevance_factors: Dict[str, Any] = field(default_factory=dict)
