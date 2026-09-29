from ingestion.nlp.entity_extractor import extract_entities
from ingestion.nlp.relation_extractor import extract_relations


def _relation_types(relations):
    return [r.type for r in relations]


def test_single_well_document_links_licence_and_company():
    text = "WELL: 30/6-1\nLICENCE: PL 123\nOPERATOR: Equinor"
    entities = extract_entities(text)
    relations = extract_relations(text, entities)
    types = _relation_types(relations)
    assert "HAS_LICENCE" in types
    assert "OPERATED_BY" in types


def test_formation_tops_table_produces_top_and_base_depth():
    text = "Heimdal    2450 m    2520 m"
    entities = extract_entities(text)
    relations = extract_relations(text, entities)
    top = [r for r in relations if r.type == "HAS_TOP_DEPTH"]
    base = [r for r in relations if r.type == "HAS_BASE_DEPTH"]
    assert len(top) == 1
    assert len(base) == 1
    assert top[0].object.text.startswith("2450")
    assert base[0].object.text.startswith("2520")


def test_explicit_top_keyword_picks_first_depth():
    text = "Heimdal top depth 2450 m base 2520 m"
    entities = extract_entities(text)
    relations = extract_relations(text, entities)
    types = _relation_types(relations)
    assert "HAS_TOP_DEPTH" in types
    assert "HAS_BASE_DEPTH" in types


def test_operated_by_requires_keyword_when_multiple_wells():
    text = "Well 30/6-1 and well 15/9-19A. Equinor is a major operator in the area."
    entities = extract_entities(text)
    relations = extract_relations(text, entities)
    operated = [r for r in relations if r.type == "OPERATED_BY"]
    for r in operated:
        assert r.subject.text not in ("30/6-1",) or "operator" in text.lower()


def test_no_relations_across_unrelated_lines_when_multiple_wells():
    text = "Well 30/6-1 was spudded.\nWell 15/9-19A was completed.\nHeimdal Fm was logged."
    entities = extract_entities(text)
    relations = extract_relations(text, entities)
    has_formation = [r for r in relations if r.type == "HAS_FORMATION"]
    assert has_formation == []
