from ingestion.schemas import Entity, Relation
from ingestion.validation.validators import validate_entities, validate_relations


def _entity(**overrides) -> Entity:
    defaults = dict(
        type="DEPTH", text="2450 m", normalized_value="2450 m", confidence=0.8,
        page=1, start=0, end=8, source="regex:depth",
    )
    defaults.update(overrides)
    return Entity(**defaults)


def test_flags_invalid_depth():
    entity = _entity(type="DEPTH", text="deep")
    results = validate_entities([entity])
    assert any(r.rule_name == "invalid_depth" and r.severity == "ERROR" for r in results)


def test_flags_unparseable_date():
    entity = _entity(type="DATE", text="not-a-date")
    results = validate_entities([entity])
    assert any(r.rule_name == "unparseable_date" for r in results)


def test_flags_invalid_well_id():
    entity = _entity(type="WELL", text="not-a-well-id")
    results = validate_entities([entity])
    assert any(r.rule_name == "invalid_well_id" and r.severity == "ERROR" for r in results)


def test_valid_well_id_does_not_flag():
    entity = _entity(type="WELL", text="30/6-1")
    results = validate_entities([entity])
    assert not any(r.rule_name == "invalid_well_id" for r in results)


def test_flags_unresolved_resolvable_entity():
    entity = _entity(type="COMPANY", text="Unknown Corp", resolution_status="UNRESOLVED")
    results = validate_entities([entity])
    assert any(r.rule_name == "unresolved_entity" for r in results)


def test_flags_duplicate_entities():
    e1 = _entity(type="WELL", text="30/6-1", normalized_value="30/6-1", start=0, end=6)
    e2 = _entity(type="WELL", text="30/6-1", normalized_value="30/6-1", start=20, end=26)
    results = validate_entities([e1, e2])
    assert any(r.rule_name == "duplicate_entity" for r in results)


def test_formation_top_below_base_flagged_as_error():
    formation = _entity(type="FORMATION", text="Heimdal", normalized_value="Heimdal")
    top_depth = _entity(type="DEPTH", text="2520 m")
    base_depth = _entity(type="DEPTH", text="2450 m")
    relations = [
        Relation(type="HAS_TOP_DEPTH", subject=formation, object=top_depth, confidence=0.6,
                 page=1, source="test"),
        Relation(type="HAS_BASE_DEPTH", subject=formation, object=base_depth, confidence=0.6,
                 page=1, source="test"),
    ]
    results = validate_relations(relations)
    assert any(r.rule_name == "formation_depth_order" and r.severity == "ERROR" for r in results)


def test_correct_formation_depth_order_not_flagged():
    formation = _entity(type="FORMATION", text="Heimdal", normalized_value="Heimdal")
    top_depth = _entity(type="DEPTH", text="2450 m")
    base_depth = _entity(type="DEPTH", text="2520 m")
    relations = [
        Relation(type="HAS_TOP_DEPTH", subject=formation, object=top_depth, confidence=0.6,
                 page=1, source="test"),
        Relation(type="HAS_BASE_DEPTH", subject=formation, object=base_depth, confidence=0.6,
                 page=1, source="test"),
    ]
    results = validate_relations(relations)
    assert not any(r.rule_name == "formation_depth_order" for r in results)
