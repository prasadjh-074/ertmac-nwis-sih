from ingestion.normalization.name_normalizer import (
    normalize_company_name,
    normalize_formation_name,
    normalize_licence_name,
    normalize_well_name,
)


def test_normalize_formation_strips_suffix_variants():
    assert normalize_formation_name("HEIMDAL FM") == "Heimdal"
    assert normalize_formation_name("Heimdal Fm.") == "Heimdal"
    assert normalize_formation_name("Heimdal Formation") == "Heimdal"


def test_normalize_company_maps_historical_alias():
    assert normalize_company_name("Statoil") == "Equinor"
    assert normalize_company_name("Equinor ASA") == "Equinor"


def test_normalize_company_falls_back_to_title_case_for_unknown():
    assert normalize_company_name("random drilling co") == "Random Drilling Co"


def test_normalize_well_name_removes_stray_whitespace():
    assert normalize_well_name("30 / 6-1") == "30/6-1"
    assert normalize_well_name("30/6-1") == "30/6-1"


def test_normalize_licence_name_variants():
    assert normalize_licence_name("PL123") == "PL 123"
    assert normalize_licence_name("pl 123") == "PL 123"
    assert normalize_licence_name("PL 123") == "PL 123"
