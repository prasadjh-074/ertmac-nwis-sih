"""Typed result models for the query resolver."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WellMatch(BaseModel):
    """A single well from a similarity search."""
    dataset: str
    well_id: str
    similarity: float
    rank: int
    windows_total: int
    windows_pooled: int
    pooling_fraction: float


class WindowMatch(BaseModel):
    """A single window from a similarity search."""
    dataset: str
    well_id: str
    window_id: int
    depth_start_m: Optional[float] = None
    depth_end_m: Optional[float] = None
    similarity: float
    rank: int
    curves_present: int


class WellInfo(BaseModel):
    """Well metadata from SODIR and/or the identity bridge."""
    dataset: str
    well_id: str
    source_system: str
    sodir_wellbore_id: Optional[int] = None
    sodir_wellbore_name: Optional[str] = None
    match_method: Optional[str] = None
    wellbore_type: Optional[str] = None
    purpose: Optional[str] = None
    status: Optional[str] = None
    operator: Optional[str] = None
    field_name: Optional[str] = None
    field_id: Optional[int] = None
    discovery_name: Optional[str] = None
    discovery_id: Optional[int] = None
    licence_name: Optional[str] = None
    licence_id: Optional[int] = None
    total_depth_m: Optional[float] = None
    water_depth_m: Optional[float] = None
    spud_date: Optional[str] = None
    completion_date: Optional[str] = None
    companies: List[CompanyRole] = []


class CompanyRole(BaseModel):
    """A company's role on a wellbore."""
    company_name: str
    role: str


WellInfo.model_rebuild()


class FormationTop(BaseModel):
    """A single formation top from SODIR."""
    source_system: str = "SODIR"
    formation_name: Optional[str] = None
    formation_id: Optional[int] = None
    top_depth_m: Optional[float] = None
    base_depth_m: Optional[float] = None
    parent_formation_name: Optional[str] = None
    stratigraphic_age: Optional[str] = None


class CompareWellsResult(BaseModel):
    """Side-by-side comparison of two wells."""
    target: WellInfo
    comparison: WellInfo
    similarity: Optional[float] = None


class GeologicalContextGroup(BaseModel):
    """A group of geological context data for one entity type."""
    entity_type: str
    source_system: str = "SODIR"
    records: List[Dict[str, Any]] = []
    record_count: int = 0


class ResolutionResult(BaseModel):
    """Top-level result from the resolver."""
    intent: str
    status: str
    query: Dict[str, Any]
    results: Any
    result_count: int
    sources: List[str]
    metadata: Dict[str, Any] = {}
