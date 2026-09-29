from ingestion.nlp.entity_extractor import extract_entities


def _types(entities):
    return [e.type for e in entities]


def test_extracts_well_id():
    entities = extract_entities("The well 30/6-1 was drilled in 2001.")
    wells = [e for e in entities if e.type == "WELL"]
    assert len(wells) == 1
    assert wells[0].text == "30/6-1"


def test_extracts_licence():
    entities = extract_entities("Licence: PL 123 was awarded.")
    licences = [e for e in entities if e.type == "LICENCE"]
    assert len(licences) == 1
    assert licences[0].normalized_value == "PL 123"


def test_extracts_formation_with_suffix():
    entities = extract_entities("The Heimdal Fm. was encountered at depth.")
    formations = [e for e in entities if e.type == "FORMATION"]
    assert len(formations) == 1
    assert formations[0].normalized_value == "Heimdal"


def test_extracts_bare_known_formation_name_without_suffix():
    entities = extract_entities("Heimdal    2450 m    2520 m")
    formations = [e for e in entities if e.type == "FORMATION"]
    assert len(formations) == 1
    assert formations[0].normalized_value == "Heimdal"


def test_does_not_double_count_formation_with_suffix():
    entities = extract_entities("Heimdal Fm was logged.")
    formations = [e for e in entities if e.type == "FORMATION"]
    assert len(formations) == 1


def test_extracts_depth_with_unit():
    entities = extract_entities("Total depth 2890 m was reached.")
    depths = [e for e in entities if e.type == "DEPTH"]
    assert len(depths) == 1
    assert "2890" in depths[0].text


def test_extracts_date_dot_format():
    entities = extract_entities("Spud date: 12.03.2001")
    dates = [e for e in entities if e.type == "DATE"]
    assert len(dates) == 1
    assert dates[0].text == "12.03.2001"


def test_extracts_date_month_name_format():
    entities = extract_entities("Completed on 12 March 2001.")
    dates = [e for e in entities if e.type == "DATE"]
    assert len(dates) == 1


def test_extracts_company_via_alias():
    entities = extract_entities("Operator: Equinor")
    companies = [e for e in entities if e.type == "COMPANY"]
    assert len(companies) == 1
    assert companies[0].normalized_value == "Equinor"


def test_extracts_company_via_historical_alias():
    entities = extract_entities("Operated by Statoil at the time.")
    companies = [e for e in entities if e.type == "COMPANY"]
    assert len(companies) == 1
    assert companies[0].normalized_value == "Equinor"


def test_extracts_field_via_alias():
    entities = extract_entities("Located in the Volve field.")
    fields = [e for e in entities if e.type == "FIELD"]
    assert len(fields) == 1
    assert fields[0].normalized_value == "Volve"


def test_extracts_log_curve():
    entities = extract_entities("GR and RHOB logs were run.")
    curves = [e for e in entities if e.type == "LOG_CURVE"]
    assert {e.text for e in curves} == {"GR", "RHOB"}


def test_extracts_production_value():
    entities = extract_entities("Production reached 1200 bbl/d in the first month.")
    productions = [e for e in entities if e.type == "PRODUCTION"]
    assert len(productions) == 1


def test_combined_fixture_example_from_brief():
    entities = extract_entities("Heimdal Fm. 2450 m")
    types = _types(entities)
    assert "FORMATION" in types
    assert "DEPTH" in types
