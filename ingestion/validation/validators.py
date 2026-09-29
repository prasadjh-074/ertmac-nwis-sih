"""Basic, explainable validation rules over extracted entities/relations.
Never silently discards bad data -- every issue becomes a ValidationResult
(INFO/WARNING/ERROR) that gets persisted, not just logged.
"""
from __future__ import annotations

from ingestion.nlp.entity_extractor import WELL_ID_RE
from ingestion.normalization.unit_normalizer import parse_date, parse_length
from ingestion.schemas import Entity, Relation, ValidationResult

RESOLVABLE_ENTITY_TYPES = {"WELL", "LICENCE", "COMPANY", "FIELD"}


def _formation_key(entity: Entity) -> str:
    return (entity.normalized_value or entity.text).lower()


def validate_entities(entities: list[Entity]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    seen: set[tuple[str, str, int | None]] = set()

    for e in entities:
        dedup_key = (e.type, (e.normalized_value or e.text).lower(), e.page)
        if dedup_key in seen:
            results.append(ValidationResult(
                rule_name="duplicate_entity", severity="WARNING",
                message=f"Duplicate {e.type} entity '{e.text}' on page {e.page}",
                context={"type": e.type, "text": e.text, "page": e.page},
            ))
        else:
            seen.add(dedup_key)

        if e.type == "DEPTH" and parse_length(e.text) is None:
            results.append(ValidationResult(
                rule_name="invalid_depth", severity="ERROR",
                message=f"Depth value '{e.text}' is not numeric or has an unrecognized unit",
                context={"text": e.text, "page": e.page},
            ))

        if e.type == "DATE" and parse_date(e.text) is None:
            results.append(ValidationResult(
                rule_name="unparseable_date", severity="WARNING",
                message=f"Date '{e.text}' could not be parsed with any known format",
                context={"text": e.text, "page": e.page},
            ))

        if e.type == "WELL" and not WELL_ID_RE.fullmatch(e.text):
            results.append(ValidationResult(
                rule_name="invalid_well_id", severity="ERROR",
                message=f"Well identifier '{e.text}' does not match the expected NPD-style pattern",
                context={"text": e.text, "page": e.page},
            ))

        if e.resolution_status == "UNRESOLVED" and e.type in RESOLVABLE_ENTITY_TYPES:
            results.append(ValidationResult(
                rule_name="unresolved_entity", severity="WARNING",
                message=f"{e.type} '{e.text}' could not be resolved against the reference dataset",
                context={"type": e.type, "text": e.text, "page": e.page},
            ))

    return results


def validate_relations(relations: list[Relation]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    tops: dict[str, float] = {}
    bases: dict[str, float] = {}

    for r in relations:
        if r.type == "HAS_TOP_DEPTH":
            depth = parse_length(r.object.text)
            if depth is not None:
                tops[_formation_key(r.subject)] = depth
        elif r.type == "HAS_BASE_DEPTH":
            depth = parse_length(r.object.text)
            if depth is not None:
                bases[_formation_key(r.subject)] = depth

    for key in tops.keys() & bases.keys():
        if tops[key] >= bases[key]:
            results.append(ValidationResult(
                rule_name="formation_depth_order", severity="ERROR",
                message=(
                    f"Formation '{key}' top depth ({tops[key]}m) is not "
                    f"above its base depth ({bases[key]}m)"
                ),
                context={"formation": key, "top_m": tops[key], "base_m": bases[key]},
            ))

    return results


def validate(entities: list[Entity], relations: list[Relation]) -> list[ValidationResult]:
    return validate_entities(entities) + validate_relations(relations)
