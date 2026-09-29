"""Typed models for the nearby-well system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class WellLocation:
    """A well's geographic identity and coordinates.

    latitude/longitude may be None when the well has no SODIR link or the
    SODIR record lacks coordinates.  Code consuming WellLocation must
    handle the None case explicitly — coordinates are never fabricated.
    """

    well_id: str
    dataset: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    sodir_wellbore_id: Optional[int] = None
    sodir_wellbore_name: Optional[str] = None
    field_name: Optional[str] = None
    field_id: Optional[int] = None
    discovery_name: Optional[str] = None
    discovery_id: Optional[int] = None

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


@dataclass
class NearbyWellResult:
    """One well returned from a nearby-well search."""

    well_id: str
    dataset: str
    latitude: float
    longitude: float
    distance_km: float
    sodir_wellbore_id: Optional[int] = None
    sodir_wellbore_name: Optional[str] = None
    field_name: Optional[str] = None
    discovery_name: Optional[str] = None
    rank: int = 0


@dataclass
class CombinedNearbyResult:
    """A nearby well enriched with geological similarity from the existing
    embedding engine.  Both metrics are exposed independently — no opaque
    combined score is produced without showing its components."""

    well_id: str
    dataset: str
    latitude: float
    longitude: float
    distance_km: float
    similarity: Optional[float] = None
    combined_relevance: Optional[float] = None
    distance_weight: float = 0.0
    similarity_weight: float = 0.0
    sodir_wellbore_id: Optional[int] = None
    field_name: Optional[str] = None
    discovery_name: Optional[str] = None
    rank: int = 0


@dataclass
class CurrentWellState:
    """Snapshot of a well's current operational state.

    Fields that are unavailable remain None — never fabricated.
    ``is_simulated`` distinguishes synthetic demo data from real
    observations; production code must check this flag.
    """

    well_id: str
    dataset: str
    timestamp: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    current_depth_m: Optional[float] = None
    current_formation: Optional[str] = None
    total_depth_m: Optional[float] = None
    status: Optional[str] = None
    operator: Optional[str] = None
    field_name: Optional[str] = None
    drilling_parameters: Dict[str, Any] = field(default_factory=dict)
    is_simulated: bool = False
