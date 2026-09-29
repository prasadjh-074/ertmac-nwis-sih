import pytest

from ingestion.normalization.unit_normalizer import normalize_length, parse_date, parse_length


def test_normalize_length_km_to_meters():
    assert normalize_length(2.89, "km") == 2890.0


def test_normalize_length_cm_to_meters():
    assert normalize_length(289000, "cm") == 2890.0


def test_normalize_length_unknown_unit_raises():
    with pytest.raises(ValueError):
        normalize_length(10, "furlongs")


def test_parse_length_extracts_value_and_converts():
    assert parse_length("2.89 km") == 2890.0
    assert parse_length("2890 m") == 2890.0
    assert parse_length("total depth 2890 m reached") == 2890.0


def test_parse_length_returns_none_for_unparseable():
    assert parse_length("no numbers here") is None


def test_parse_date_multiple_formats():
    assert parse_date("12.03.2001") == "2001-03-12"
    assert parse_date("2001-03-12") == "2001-03-12"
    assert parse_date("12 March 2001") == "2001-03-12"
    assert parse_date("March 12, 2001") == "2001-03-12"


def test_parse_date_returns_none_without_raising():
    assert parse_date("not a date") is None
