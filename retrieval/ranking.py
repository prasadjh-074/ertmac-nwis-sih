"""
Result shaping and ranking for the retrieval layer.

Ranking here means exactly one thing, per instructions: cosine similarity,
descending. No weighting formula, no reranking model. These dataclasses
carry every field needed to explain a result (§ explainability) without
generating any natural-language text.
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass
class WindowResult:
    dataset: str
    well_id: str
    window_id: int
    depth_start_m: Optional[float]
    depth_end_m: Optional[float]
    similarity: float
    rank: int
    curves_present: int
    embedding_type: str


@dataclass
class WellResult:
    dataset: str
    well_id: str
    similarity: float
    rank: int
    windows_total: int
    windows_pooled: int
    windows_excluded: int
    pooling_fraction: float


def rank_window_rows(rows: Sequence[Tuple]) -> List[WindowResult]:
    """rows must already be ordered by cosine distance ascending (i.e.
    similarity descending) - this only assigns the 1-indexed rank, it does
    not re-sort anything."""

    results = []
    for i, row in enumerate(rows, start=1):
        dataset, well_id, window_id, depth_start_m, depth_end_m, cosine_distance, curves_present, embedding_type = row
        results.append(
            WindowResult(
                dataset=dataset,
                well_id=well_id,
                window_id=window_id,
                depth_start_m=depth_start_m,
                depth_end_m=depth_end_m,
                similarity=1.0 - float(cosine_distance),
                rank=i,
                curves_present=curves_present,
                embedding_type=embedding_type,
            )
        )
    return results


def rank_well_rows(rows: Sequence[Tuple]) -> List[WellResult]:
    results = []
    for i, row in enumerate(rows, start=1):
        dataset, well_id, cosine_distance, windows_total, windows_pooled, windows_excluded, pooling_fraction = row
        results.append(
            WellResult(
                dataset=dataset,
                well_id=well_id,
                similarity=1.0 - float(cosine_distance),
                rank=i,
                windows_total=windows_total,
                windows_pooled=windows_pooled,
                windows_excluded=windows_excluded,
                pooling_fraction=float(pooling_fraction),
            )
        )
    return results
