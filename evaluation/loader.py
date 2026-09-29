"""Load and validate the golden query dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from .models import GoldenDataset, GoldenQuery

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "evaluation" / "golden_queries.json"


def load_golden_dataset(path: Optional[Path] = None) -> GoldenDataset:
    p = path or _DEFAULT_PATH
    with open(p) as f:
        raw = json.load(f)
    return GoldenDataset.model_validate(raw)


def filter_queries(
    dataset: GoldenDataset,
    *,
    intent: Optional[str] = None,
    tags: Optional[List[str]] = None,
    exclude_tags: Optional[List[str]] = None,
    ids: Optional[List[str]] = None,
) -> List[GoldenQuery]:
    result = dataset.queries
    if intent:
        result = [q for q in result if q.intent == intent]
    if tags:
        result = [q for q in result if set(tags) & set(q.tags)]
    if exclude_tags:
        result = [q for q in result if not (set(exclude_tags) & set(q.tags))]
    if ids:
        id_set = set(ids)
        result = [q for q in result if q.id in id_set]
    return result
