"""Loaders for the ontology YAML files (entities, aliases, relationships,
units). Kept tiny -- just a cached YAML reader other modules build indexes
from at import time.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_ONTOLOGY_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_yaml(filename: str) -> dict:
    path = _ONTOLOGY_DIR / filename
    with open(path, "r") as f:
        return yaml.safe_load(f)


def entities() -> list[str]:
    return load_yaml("entities.yaml")["entity_types"]


def aliases() -> dict:
    return load_yaml("aliases.yaml")


def relationships() -> list[dict]:
    return load_yaml("relationships.yaml")["relation_types"]


def units() -> dict:
    return load_yaml("units.yaml")
