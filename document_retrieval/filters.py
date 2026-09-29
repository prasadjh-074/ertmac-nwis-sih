"""Parameterized SQL filter builders for document chunk retrieval.

All filters compile into WHERE-clause fragments with bind parameters —
no string interpolation, no user input in SQL text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class DocumentFilters:
    """Optional constraints narrowing which document chunks are eligible."""

    source_type: Optional[str] = None
    file_name: Optional[str] = None

    def to_sql(self, alias: str = "dc") -> Tuple[List[str], List]:
        clauses: List[str] = []
        params: List = []

        if self.source_type is not None:
            clauses.append(f"d.source_type = %s")
            params.append(self.source_type)

        if self.file_name is not None:
            clauses.append(f"d.file_name = %s")
            params.append(self.file_name)

        return clauses, params


def build_where_clause(clauses: List[str]) -> str:
    if not clauses:
        return ""
    return "WHERE " + " AND ".join(clauses)
