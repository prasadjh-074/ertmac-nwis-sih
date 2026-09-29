"""Combined nearby + similar well service.

Joins geographic proximity (Haversine) with the existing geological
similarity engine (30-dim cosine embeddings from retrieval/).  Both
metrics are exposed independently — no opaque combined score is
produced unless explicitly requested, and even then the components
are always visible.
"""

from __future__ import annotations

from typing import List, Optional

from .models import CombinedNearbyResult, NearbyWellResult
from .search import find_nearby_wells, find_nearby_wells_by_coordinates, _get_connection

DEFAULT_DISTANCE_WEIGHT = 0.4
DEFAULT_SIMILARITY_WEIGHT = 0.6


def find_nearby_and_similar(
    well_id: str,
    dataset: str,
    radius_km: float = 50.0,
    limit: int = 10,
    dataset_filter: Optional[str] = None,
    include_similarity: bool = True,
    distance_weight: float = DEFAULT_DISTANCE_WEIGHT,
    similarity_weight: float = DEFAULT_SIMILARITY_WEIGHT,
    conn=None,
) -> List[CombinedNearbyResult]:
    """Find nearby wells and enrich each with geological similarity.

    The combined_relevance score (when computed) is a transparent
    weighted combination::

        combined = distance_weight * distance_score + similarity_weight * similarity
        distance_score = max(0, 1 - distance_km / radius_km)

    Both distance_km and similarity are always available as independent
    fields — the user can ignore combined_relevance entirely.

    Results are ordered by combined_relevance descending when similarity
    is included, otherwise by distance ascending.
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_connection()
    try:
        nearby = find_nearby_wells(
            well_id=well_id,
            dataset=dataset,
            radius_km=radius_km,
            limit=limit * 3 if include_similarity else limit,
            dataset_filter=dataset_filter,
            conn=conn,
        )

        if not include_similarity or not nearby:
            return [
                CombinedNearbyResult(
                    well_id=n.well_id,
                    dataset=n.dataset,
                    latitude=n.latitude,
                    longitude=n.longitude,
                    distance_km=n.distance_km,
                    similarity=None,
                    combined_relevance=None,
                    sodir_wellbore_id=n.sodir_wellbore_id,
                    field_name=n.field_name,
                    discovery_name=n.discovery_name,
                    rank=n.rank,
                )
                for n in nearby[:limit]
            ]

        sim_map = _fetch_similarities(well_id, dataset, nearby, conn=conn)

        results = []
        for n in nearby:
            sim = sim_map.get((n.dataset, n.well_id))
            distance_score = max(0.0, 1.0 - n.distance_km / radius_km) if radius_km > 0 else 1.0
            combined = None
            if sim is not None:
                combined = round(
                    distance_weight * distance_score + similarity_weight * sim,
                    4,
                )
            results.append(CombinedNearbyResult(
                well_id=n.well_id,
                dataset=n.dataset,
                latitude=n.latitude,
                longitude=n.longitude,
                distance_km=n.distance_km,
                similarity=sim,
                combined_relevance=combined,
                distance_weight=distance_weight,
                similarity_weight=similarity_weight,
                sodir_wellbore_id=n.sodir_wellbore_id,
                field_name=n.field_name,
                discovery_name=n.discovery_name,
            ))

        results.sort(key=lambda r: (
            -(r.combined_relevance if r.combined_relevance is not None else -1),
            r.distance_km,
            r.dataset,
            r.well_id,
        ))

        for i, r in enumerate(results[:limit], 1):
            r.rank = i

        return results[:limit]
    finally:
        if own_conn:
            conn.close()


def _fetch_similarities(
    well_id: str,
    dataset: str,
    nearby: List[NearbyWellResult],
    conn=None,
) -> dict:
    """Look up geological similarity between the reference well and each
    nearby well using the existing embedding engine.

    Returns {(dataset, well_id): similarity} for wells that have
    embeddings.  Wells without embeddings are simply absent from the map.
    """
    from retrieval.hybrid_search import search_similar_wells_by_id

    try:
        similar = search_similar_wells_by_id(
            dataset=dataset,
            well_id=well_id,
            top_k=50,
            conn=conn,
        )
    except Exception:
        return {}

    return {(r.dataset, r.well_id): r.similarity for r in similar}
