"""Pydantic response models for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


class WellLocationResponse(BaseModel):
    well_id: str
    dataset: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    has_coordinates: bool
    sodir_wellbore_id: Optional[int] = None
    sodir_wellbore_name: Optional[str] = None
    field_name: Optional[str] = None
    discovery_name: Optional[str] = None


class NearbyWellResponse(BaseModel):
    well_id: str
    dataset: str
    latitude: float
    longitude: float
    distance_km: float
    sodir_wellbore_id: Optional[int] = None
    sodir_wellbore_name: Optional[str] = None
    field_name: Optional[str] = None
    discovery_name: Optional[str] = None
    rank: int


class NearbyWellListResponse(BaseModel):
    reference_well: str
    reference_dataset: str
    radius_km: float
    count: int
    results: List[NearbyWellResponse]


class SimilarWellResponse(BaseModel):
    well_id: str
    dataset: str
    similarity: float
    rank: int
    windows_total: int
    windows_pooled: int
    pooling_fraction: float


class SimilarWellListResponse(BaseModel):
    reference_well: str
    reference_dataset: str
    count: int
    results: List[SimilarWellResponse]


class CombinedWellResponse(BaseModel):
    well_id: str
    dataset: str
    latitude: float
    longitude: float
    distance_km: float
    similarity: Optional[float] = None
    combined_relevance: Optional[float] = None
    distance_weight: float
    similarity_weight: float
    field_name: Optional[str] = None
    discovery_name: Optional[str] = None
    rank: int


class ContextResponse(BaseModel):
    well_id: str
    dataset: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    field_name: Optional[str] = None
    discovery_name: Optional[str] = None
    sodir_wellbore_id: Optional[int] = None
    total_depth_m: Optional[float] = None
    status: Optional[str] = None
    operator: Optional[str] = None
    nearby_well_count: int
    similar_well_count: int
    nearby_wells: List[NearbyWellResponse]
    similar_wells: List[SimilarWellResponse]


class WellListResponse(BaseModel):
    count: int
    wells: List[WellLocationResponse]


class CurrentWellStateResponse(BaseModel):
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
    drilling_parameters: Dict[str, Any] = {}
    is_simulated: bool
