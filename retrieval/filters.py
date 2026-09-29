"""
Pure metadata-filter builders for the retrieval layer.

No database connection lives here - these dataclasses only build
parameterized SQL WHERE-clause fragments (and their bind parameters), so
every filter is pushed into the SQL query itself rather than applied to
an already-fetched Python result set. This module is fully unit-testable
without a database.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class WindowFilters:
    """Optional constraints for geointelligence.window_embeddings."""

    dataset: Optional[str] = None
    well_id: Optional[str] = None
    min_curves_present: Optional[int] = None
    # (dataset, well_id, window_id) to exclude - used for query-by-example
    # so a window never appears in its own result set.
    exclude_window: Optional[Tuple[str, str, int]] = None

    def to_sql(self, alias: str = "we") -> Tuple[List[str], List]:
        clauses: List[str] = []
        params: List = []

        if self.dataset is not None:
            clauses.append(f"{alias}.dataset = %s")
            params.append(self.dataset)

        if self.well_id is not None:
            clauses.append(f"{alias}.well_id = %s")
            params.append(self.well_id)

        if self.min_curves_present is not None:
            clauses.append(f"{alias}.curves_present >= %s")
            params.append(self.min_curves_present)

        if self.exclude_window is not None:
            ex_dataset, ex_well_id, ex_window_id = self.exclude_window
            clauses.append(
                f"NOT ({alias}.dataset = %s AND {alias}.well_id = %s AND {alias}.window_id = %s)"
            )
            params.extend([ex_dataset, ex_well_id, ex_window_id])

        return clauses, params


@dataclass
class WellFilters:
    """Optional constraints for geointelligence.well_embeddings."""

    dataset: Optional[str] = None
    min_pooling_fraction: Optional[float] = None
    # (dataset, well_id) to exclude - used for query-by-example.
    exclude_well: Optional[Tuple[str, str]] = None

    def to_sql(self, alias: str = "we") -> Tuple[List[str], List]:
        clauses: List[str] = []
        params: List = []

        if self.dataset is not None:
            clauses.append(f"{alias}.dataset = %s")
            params.append(self.dataset)

        if self.min_pooling_fraction is not None:
            clauses.append(f"{alias}.pooling_fraction >= %s")
            params.append(self.min_pooling_fraction)

        if self.exclude_well is not None:
            ex_dataset, ex_well_id = self.exclude_well
            clauses.append(f"NOT ({alias}.dataset = %s AND {alias}.well_id = %s)")
            params.extend([ex_dataset, ex_well_id])

        return clauses, params


def build_where_clause(clauses: List[str]) -> str:
    """Combine filter clauses (plus any caller-supplied ones, e.g.
    embedding_type) into a single WHERE clause. Empty list -> no WHERE."""

    if not clauses:
        return ""
    return "WHERE " + " AND ".join(clauses)
