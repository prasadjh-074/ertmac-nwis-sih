"""Well-oriented endpoints:

  GET /wells                  — list wells (filter by dataset)
  GET /wells/lookup           — single well by (dataset, well_id)
  GET /wells/nearby           — Haversine radius search
  GET /wells/similar          — geological similarity via pgvector
  GET /wells/context          — well + nearby + similar in one call
  GET /wells/state            — resolved current-well state

Paths, params, and response bodies are identical to the pre-refactor
api/app.py — this router is the same contract, just wired to the
connection pool via Depends(get_conn).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from nearby.current_well import resolve_current_well
from nearby.search import find_nearby_wells, get_well_location
from retrieval.hybrid_search import search_similar_wells_by_id

from ..deps import get_conn
from ..schemas import (
    ContextResponse,
    CurrentWellStateResponse,
    NearbyWellListResponse,
    NearbyWellResponse,
    SimilarWellListResponse,
    SimilarWellResponse,
    WellListResponse,
    WellLocationResponse,
)

router = APIRouter(prefix="/wells", tags=["wells"])


@router.get("", response_model=WellListResponse)
def list_wells(
    dataset: Optional[str] = Query(None, description="Filter by dataset (FORCE_2020 or VOLVE)"),
    limit: int = Query(50, ge=1, le=500),
    conn=Depends(get_conn),
):
    cur = conn.cursor()
    clauses: list[str] = []
    params: list = []
    if dataset:
        clauses.append("wil.dataset = %s")
        params.append(dataset)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    cur.execute(
        f"""
        SELECT wil.well_id, wil.dataset,
               wb.latitude, wb.longitude,
               wb.wellbore_id, wb.wellbore_name,
               f.field_name,
               d.discovery_name,
               d.discovery_id
        FROM graph.well_identity_link wil
        JOIN core.wellbore wb ON wb.wellbore_id = wil.wellbore_id
        LEFT JOIN core.field f ON f.field_id = wb.field_id
        LEFT JOIN core.discovery d ON d.discovery_id = wb.discovery_id
        {where}
        ORDER BY wil.dataset, wil.well_id
        LIMIT %s
        """,
        params,
    )
    rows = cur.fetchall()
    wells = [
        WellLocationResponse(
            well_id=r[0], dataset=r[1],
            latitude=r[2], longitude=r[3],
            has_coordinates=r[2] is not None and r[3] is not None,
            sodir_wellbore_id=r[4], sodir_wellbore_name=r[5],
            field_name=r[6], discovery_name=r[7],
        )
        for r in rows
    ]
    return WellListResponse(count=len(wells), wells=wells)


@router.get("/lookup", response_model=WellLocationResponse)
def get_well(
    dataset: str = Query(..., description="Dataset name (FORCE_2020 or VOLVE)"),
    well_id: str = Query(..., description="Well identifier (e.g. 15/9-F-1)"),
    conn=Depends(get_conn),
):
    loc = get_well_location(well_id, dataset, conn=conn)
    if loc is None:
        raise HTTPException(status_code=404, detail=f"Well {dataset}:{well_id} not found")
    return WellLocationResponse(
        well_id=loc.well_id, dataset=loc.dataset,
        latitude=loc.latitude, longitude=loc.longitude,
        has_coordinates=loc.has_coordinates,
        sodir_wellbore_id=loc.sodir_wellbore_id,
        sodir_wellbore_name=loc.sodir_wellbore_name,
        field_name=loc.field_name, discovery_name=loc.discovery_name,
    )


@router.get("/nearby", response_model=NearbyWellListResponse)
def get_nearby(
    dataset: str = Query(..., description="Dataset name"),
    well_id: str = Query(..., description="Well identifier"),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(10, ge=1, le=50),
    dataset_filter: Optional[str] = Query(None),
    conn=Depends(get_conn),
):
    try:
        results = find_nearby_wells(
            well_id=well_id, dataset=dataset,
            radius_km=radius_km, limit=limit,
            dataset_filter=dataset_filter, conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return NearbyWellListResponse(
        reference_well=well_id, reference_dataset=dataset,
        radius_km=radius_km, count=len(results),
        results=[
            NearbyWellResponse(
                well_id=r.well_id, dataset=r.dataset,
                latitude=r.latitude, longitude=r.longitude,
                distance_km=r.distance_km,
                sodir_wellbore_id=r.sodir_wellbore_id,
                sodir_wellbore_name=r.sodir_wellbore_name,
                field_name=r.field_name, discovery_name=r.discovery_name,
                rank=r.rank,
            )
            for r in results
        ],
    )


@router.get("/similar", response_model=SimilarWellListResponse)
def get_similar(
    dataset: str = Query(..., description="Dataset name"),
    well_id: str = Query(..., description="Well identifier"),
    top_k: int = Query(10, ge=1, le=50),
    dataset_filter: Optional[str] = Query(None),
    conn=Depends(get_conn),
):
    try:
        results = search_similar_wells_by_id(
            dataset=dataset, well_id=well_id,
            top_k=top_k, dataset_filter=dataset_filter, conn=conn,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return SimilarWellListResponse(
        reference_well=well_id, reference_dataset=dataset,
        count=len(results),
        results=[
            SimilarWellResponse(
                well_id=r.well_id, dataset=r.dataset,
                similarity=round(r.similarity, 4), rank=r.rank,
                windows_total=r.windows_total, windows_pooled=r.windows_pooled,
                pooling_fraction=round(r.pooling_fraction, 4),
            )
            for r in results
        ],
    )


@router.get("/context", response_model=ContextResponse)
def get_context(
    dataset: str = Query(..., description="Dataset name"),
    well_id: str = Query(..., description="Well identifier"),
    radius_km: float = Query(50.0, gt=0, le=500),
    nearby_limit: int = Query(5, ge=1, le=20),
    similar_limit: int = Query(5, ge=1, le=20),
    conn=Depends(get_conn),
):
    loc = get_well_location(well_id, dataset, conn=conn)
    if loc is None:
        raise HTTPException(status_code=404, detail=f"Well {dataset}:{well_id} not found")

    cur = conn.cursor()
    total_depth = None
    status = None
    operator = None
    if loc.sodir_wellbore_id:
        cur.execute(
            "SELECT total_depth_m, status, operator FROM core.wellbore WHERE wellbore_id = %s",
            (loc.sodir_wellbore_id,),
        )
        row = cur.fetchone()
        if row:
            total_depth, status, operator = row

    nearby = []
    if loc.has_coordinates:
        try:
            nearby_results = find_nearby_wells(
                well_id=well_id, dataset=dataset,
                radius_km=radius_km, limit=nearby_limit, conn=conn,
            )
            nearby = [
                NearbyWellResponse(
                    well_id=r.well_id, dataset=r.dataset,
                    latitude=r.latitude, longitude=r.longitude,
                    distance_km=r.distance_km,
                    sodir_wellbore_id=r.sodir_wellbore_id,
                    sodir_wellbore_name=r.sodir_wellbore_name,
                    field_name=r.field_name, discovery_name=r.discovery_name,
                    rank=r.rank,
                )
                for r in nearby_results
            ]
        except ValueError:
            pass

    similar = []
    try:
        similar_results = search_similar_wells_by_id(
            dataset=dataset, well_id=well_id,
            top_k=similar_limit, conn=conn,
        )
        similar = [
            SimilarWellResponse(
                well_id=r.well_id, dataset=r.dataset,
                similarity=round(r.similarity, 4), rank=r.rank,
                windows_total=r.windows_total, windows_pooled=r.windows_pooled,
                pooling_fraction=round(r.pooling_fraction, 4),
            )
            for r in similar_results
        ]
    except Exception:
        pass

    return ContextResponse(
        well_id=well_id, dataset=dataset,
        latitude=loc.latitude, longitude=loc.longitude,
        field_name=loc.field_name, discovery_name=loc.discovery_name,
        sodir_wellbore_id=loc.sodir_wellbore_id,
        total_depth_m=total_depth, status=status, operator=operator,
        nearby_well_count=len(nearby), similar_well_count=len(similar),
        nearby_wells=nearby, similar_wells=similar,
    )


@router.get("/state", response_model=CurrentWellStateResponse)
def get_well_state(
    dataset: str = Query(..., description="Dataset name"),
    well_id: str = Query(..., description="Well identifier"),
    conn=Depends(get_conn),
):
    state = resolve_current_well(well_id, dataset, conn=conn)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Well {dataset}:{well_id} not found")
    return CurrentWellStateResponse(
        well_id=state.well_id, dataset=state.dataset,
        timestamp=state.timestamp,
        latitude=state.latitude, longitude=state.longitude,
        current_depth_m=state.current_depth_m,
        current_formation=state.current_formation,
        total_depth_m=state.total_depth_m,
        status=state.status, operator=state.operator,
        field_name=state.field_name,
        drilling_parameters=state.drilling_parameters,
        is_simulated=state.is_simulated,
    )
