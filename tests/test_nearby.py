"""Tests for the nearby-well intelligence system."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from nearby.models import (
    CombinedNearbyResult,
    CurrentWellState,
    NearbyWellResult,
    WellLocation,
)
from nearby.search import haversine_km


# ============================================================
# Haversine unit tests (no database)
# ============================================================

class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_km(60.0, 3.0, 60.0, 3.0) == 0.0

    def test_known_distance_oslo_bergen(self):
        # Oslo (59.91, 10.75) to Bergen (60.39, 5.32): ~305 km
        d = haversine_km(59.91, 10.75, 60.39, 5.32)
        assert 300 < d < 310

    def test_known_distance_short(self):
        # Two points ~1 km apart on the NCS
        d = haversine_km(60.0, 3.0, 60.009, 3.0)
        assert 0.5 < d < 1.5

    def test_symmetry(self):
        d1 = haversine_km(60.0, 3.0, 61.0, 4.0)
        d2 = haversine_km(61.0, 4.0, 60.0, 3.0)
        assert d1 == pytest.approx(d2, abs=1e-10)

    def test_equator_one_degree(self):
        # 1 degree of longitude at equator is ~111.2 km
        d = haversine_km(0.0, 0.0, 0.0, 1.0)
        assert 110 < d < 112

    def test_negative_coordinates(self):
        d = haversine_km(-33.87, 151.21, -33.87, 151.21)
        assert d == 0.0

    def test_antipodal_points(self):
        d = haversine_km(0.0, 0.0, 0.0, 180.0)
        assert 20000 < d < 20100


# ============================================================
# WellLocation model tests (no database)
# ============================================================

class TestWellLocation:
    def test_has_coordinates_true(self):
        loc = WellLocation(well_id="A", dataset="VOLVE", latitude=60.0, longitude=3.0)
        assert loc.has_coordinates is True

    def test_has_coordinates_false_no_lat(self):
        loc = WellLocation(well_id="A", dataset="VOLVE", latitude=None, longitude=3.0)
        assert loc.has_coordinates is False

    def test_has_coordinates_false_no_lon(self):
        loc = WellLocation(well_id="A", dataset="VOLVE", latitude=60.0, longitude=None)
        assert loc.has_coordinates is False

    def test_has_coordinates_false_both_none(self):
        loc = WellLocation(well_id="A", dataset="VOLVE")
        assert loc.has_coordinates is False

    def test_optional_fields_default_none(self):
        loc = WellLocation(well_id="A", dataset="VOLVE")
        assert loc.sodir_wellbore_id is None
        assert loc.field_name is None
        assert loc.discovery_name is None


# ============================================================
# NearbyWellResult model tests (no database)
# ============================================================

class TestNearbyWellResult:
    def test_creation(self):
        r = NearbyWellResult(
            well_id="15/9-F-1", dataset="VOLVE",
            latitude=58.44, longitude=1.89,
            distance_km=0.5, rank=1,
        )
        assert r.distance_km == 0.5
        assert r.rank == 1

    def test_optional_sodir_fields(self):
        r = NearbyWellResult(
            well_id="X", dataset="FORCE_2020",
            latitude=60.0, longitude=3.0,
            distance_km=10.0,
        )
        assert r.sodir_wellbore_id is None
        assert r.field_name is None


# ============================================================
# CurrentWellState model tests (no database)
# ============================================================

class TestCurrentWellState:
    def test_simulated_flag(self):
        from nearby.current_well import create_simulated_well
        state = create_simulated_well(
            well_id="SIM-1", dataset="DEMO",
            latitude=60.0, longitude=3.0,
            current_depth_m=2500.0,
            current_formation="Utsira",
        )
        assert state.is_simulated is True
        assert state.well_id == "SIM-1"
        assert state.current_depth_m == 2500.0
        assert state.current_formation == "Utsira"

    def test_simulated_drilling_parameters(self):
        from nearby.current_well import create_simulated_well
        state = create_simulated_well(
            well_id="SIM-2", dataset="DEMO",
            latitude=60.0, longitude=3.0,
            drilling_parameters={"wob_kN": 120, "rpm": 60},
        )
        assert state.drilling_parameters["wob_kN"] == 120
        assert state.is_simulated is True

    def test_missing_fields_explicit(self):
        state = CurrentWellState(
            well_id="X", dataset="VOLVE",
            timestamp=datetime.now(timezone.utc),
        )
        assert state.current_depth_m is None
        assert state.current_formation is None
        assert state.operator is None
        assert state.drilling_parameters == {}


# ============================================================
# Radius filtering and ordering tests (mocked DB)
# ============================================================

def _make_candidates():
    """Fake candidate wells at known positions near (60.0, 3.0)."""
    return [
        {"well_id": "A", "dataset": "FORCE_2020", "latitude": 60.009, "longitude": 3.0,
         "sodir_wellbore_id": 1, "sodir_wellbore_name": "A", "field_name": "F1", "discovery_name": None},
        {"well_id": "B", "dataset": "FORCE_2020", "latitude": 60.045, "longitude": 3.0,
         "sodir_wellbore_id": 2, "sodir_wellbore_name": "B", "field_name": "F1", "discovery_name": None},
        {"well_id": "C", "dataset": "VOLVE", "latitude": 60.45, "longitude": 3.0,
         "sodir_wellbore_id": 3, "sodir_wellbore_name": "C", "field_name": "F2", "discovery_name": None},
        {"well_id": "D", "dataset": "FORCE_2020", "latitude": 61.0, "longitude": 4.0,
         "sodir_wellbore_id": 4, "sodir_wellbore_name": "D", "field_name": "F3", "discovery_name": None},
    ]


class TestRadiusFiltering:
    @patch("nearby.search._fetch_candidate_wells", return_value=_make_candidates())
    def test_radius_filters_correctly(self, mock_fetch):
        from nearby.search import find_nearby_wells_by_coordinates
        # Well A is ~1 km away, well B is ~5 km, well C is ~50 km, well D is ~125 km
        results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=6.0, limit=10)
        assert len(results) == 2
        assert results[0].well_id == "A"
        assert results[1].well_id == "B"

    @patch("nearby.search._fetch_candidate_wells", return_value=_make_candidates())
    def test_large_radius_returns_all(self, mock_fetch):
        from nearby.search import find_nearby_wells_by_coordinates
        results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=500.0, limit=10)
        assert len(results) == 4

    @patch("nearby.search._fetch_candidate_wells", return_value=_make_candidates())
    def test_zero_radius_returns_none(self, mock_fetch):
        from nearby.search import find_nearby_wells_by_coordinates
        results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=0.001, limit=10)
        assert len(results) == 0


class TestNearestN:
    @patch("nearby.search._fetch_candidate_wells", return_value=_make_candidates())
    def test_limit_caps_results(self, mock_fetch):
        from nearby.search import find_nearby_wells_by_coordinates
        results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=500.0, limit=2)
        assert len(results) == 2

    @patch("nearby.search._fetch_candidate_wells", return_value=_make_candidates())
    def test_limit_one_returns_closest(self, mock_fetch):
        from nearby.search import find_nearby_wells_by_coordinates
        results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=500.0, limit=1)
        assert results[0].well_id == "A"


class TestDeterministicOrdering:
    @patch("nearby.search._fetch_candidate_wells", return_value=_make_candidates())
    def test_ordered_by_distance_ascending(self, mock_fetch):
        from nearby.search import find_nearby_wells_by_coordinates
        results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=500.0, limit=10)
        distances = [r.distance_km for r in results]
        assert distances == sorted(distances)

    @patch("nearby.search._fetch_candidate_wells", return_value=_make_candidates())
    def test_ranks_are_sequential(self, mock_fetch):
        from nearby.search import find_nearby_wells_by_coordinates
        results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=500.0, limit=10)
        ranks = [r.rank for r in results]
        assert ranks == list(range(1, len(results) + 1))

    def test_tie_breaking_by_dataset_then_well_id(self):
        # Two wells at identical distance
        candidates = [
            {"well_id": "Z", "dataset": "VOLVE", "latitude": 60.009, "longitude": 3.0,
             "sodir_wellbore_id": 1, "sodir_wellbore_name": "Z", "field_name": None, "discovery_name": None},
            {"well_id": "A", "dataset": "FORCE_2020", "latitude": 60.009, "longitude": 3.0,
             "sodir_wellbore_id": 2, "sodir_wellbore_name": "A", "field_name": None, "discovery_name": None},
        ]
        with patch("nearby.search._fetch_candidate_wells", return_value=candidates):
            from nearby.search import find_nearby_wells_by_coordinates
            results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=500.0, limit=10)
            # FORCE_2020 sorts before VOLVE
            assert results[0].dataset == "FORCE_2020"
            assert results[1].dataset == "VOLVE"


class TestMissingCoordinates:
    def test_candidates_without_coords_excluded(self):
        candidates = [
            {"well_id": "A", "dataset": "X", "latitude": 60.0, "longitude": 3.0,
             "sodir_wellbore_id": 1, "sodir_wellbore_name": "A", "field_name": None, "discovery_name": None},
            {"well_id": "B", "dataset": "X", "latitude": None, "longitude": None,
             "sodir_wellbore_id": 2, "sodir_wellbore_name": "B", "field_name": None, "discovery_name": None},
        ]
        with patch("nearby.search._fetch_candidate_wells", return_value=candidates):
            from nearby.search import find_nearby_wells_by_coordinates
            results = find_nearby_wells_by_coordinates(60.0, 3.0, radius_km=500.0, limit=10)
            assert len(results) == 1
            assert results[0].well_id == "A"


class TestDatasetFiltering:
    @patch("nearby.search._fetch_candidate_wells", return_value=_make_candidates())
    def test_dataset_filter_passed_through(self, mock_fetch):
        from nearby.search import find_nearby_wells_by_coordinates
        find_nearby_wells_by_coordinates(
            60.0, 3.0, radius_km=500.0, limit=10, dataset_filter="VOLVE",
        )
        # _fetch_candidate_wells was called with the filter
        call_args = mock_fetch.call_args
        assert call_args[0][0] == "VOLVE" or call_args[1].get("dataset_filter") == "VOLVE"


class TestDuplicateWells:
    def test_self_excluded_from_by_id_search(self):
        candidates = [
            {"well_id": "TARGET", "dataset": "VOLVE", "latitude": 60.0, "longitude": 3.0,
             "sodir_wellbore_id": 1, "sodir_wellbore_name": "T", "field_name": None, "discovery_name": None},
            {"well_id": "OTHER", "dataset": "VOLVE", "latitude": 60.009, "longitude": 3.0,
             "sodir_wellbore_id": 2, "sodir_wellbore_name": "O", "field_name": None, "discovery_name": None},
        ]
        with patch("nearby.search._fetch_candidate_wells", return_value=candidates):
            from nearby.search import find_nearby_wells_by_coordinates
            results = find_nearby_wells_by_coordinates(
                60.0, 3.0, radius_km=500.0, limit=10,
                exclude_well=("TARGET", "VOLVE"),
            )
            well_ids = [r.well_id for r in results]
            assert "TARGET" not in well_ids


# ============================================================
# Combined nearby + similarity tests (mocked)
# ============================================================

class TestCombinedNearbyResult:
    def test_creation_with_both_metrics(self):
        r = CombinedNearbyResult(
            well_id="A", dataset="VOLVE",
            latitude=60.0, longitude=3.0,
            distance_km=0.8, similarity=0.91,
            combined_relevance=0.85,
            distance_weight=0.4, similarity_weight=0.6,
        )
        assert r.distance_km == 0.8
        assert r.similarity == 0.91
        assert r.combined_relevance == 0.85

    def test_creation_without_similarity(self):
        r = CombinedNearbyResult(
            well_id="B", dataset="FORCE_2020",
            latitude=60.0, longitude=3.0,
            distance_km=3.2, similarity=None,
        )
        assert r.similarity is None
        assert r.combined_relevance is None


# ============================================================
# Integration tests (real database)
# ============================================================

@pytest.mark.integration
class TestNearbyIntegration:
    def test_get_well_location(self):
        from nearby.search import get_well_location
        loc = get_well_location("15/9-F-1", "VOLVE")
        assert loc is not None
        assert loc.has_coordinates
        assert loc.dataset == "VOLVE"
        assert 58 < loc.latitude < 59
        assert 1 < loc.longitude < 3

    def test_get_well_location_not_found(self):
        from nearby.search import get_well_location
        loc = get_well_location("NONEXISTENT", "VOLVE")
        assert loc is None

    def test_find_nearby_wells(self):
        from nearby.search import find_nearby_wells
        results = find_nearby_wells("15/9-F-1", "VOLVE", radius_km=50.0, limit=5)
        assert len(results) > 0
        for r in results:
            assert r.distance_km <= 50.0
            assert r.latitude is not None
            assert r.rank > 0
        distances = [r.distance_km for r in results]
        assert distances == sorted(distances)

    def test_find_nearby_wells_by_coordinates(self):
        from nearby.search import find_nearby_wells_by_coordinates, get_well_location
        loc = get_well_location("15/9-F-1", "VOLVE")
        results = find_nearby_wells_by_coordinates(
            loc.latitude, loc.longitude, radius_km=50.0, limit=5,
        )
        assert len(results) > 0

    def test_find_nearby_wells_dataset_filter(self):
        from nearby.search import find_nearby_wells
        results = find_nearby_wells(
            "15/9-F-1", "VOLVE", radius_km=100.0, limit=20,
            dataset_filter="VOLVE",
        )
        for r in results:
            assert r.dataset == "VOLVE"

    def test_find_nearby_wells_not_found(self):
        from nearby.search import find_nearby_wells
        with pytest.raises(ValueError, match="not found"):
            find_nearby_wells("NONEXISTENT", "VOLVE")

    def test_find_nearby_and_similar(self):
        from nearby.combined import find_nearby_and_similar
        results = find_nearby_and_similar(
            "15/9-F-1", "VOLVE", radius_km=50.0, limit=5,
        )
        assert len(results) > 0
        for r in results:
            assert r.distance_km <= 50.0
            assert r.distance_weight > 0
            assert r.similarity_weight > 0
            assert r.rank > 0

    def test_resolve_current_well(self):
        from nearby.current_well import resolve_current_well
        state = resolve_current_well("15/9-F-1", "VOLVE")
        assert state is not None
        assert state.well_id == "15/9-F-1"
        assert state.is_simulated is False
        assert state.latitude is not None

    def test_resolve_current_well_not_found(self):
        from nearby.current_well import resolve_current_well
        state = resolve_current_well("NONEXISTENT", "VOLVE")
        assert state is None


# ============================================================
# API integration tests (real database)
# ============================================================

@pytest.mark.integration
class TestAPIIntegration:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.app import app
        return TestClient(app)

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    def test_list_wells(self, client):
        resp = client.get("/wells?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 5
        assert len(data["wells"]) == data["count"]

    def test_list_wells_dataset_filter(self, client):
        resp = client.get("/wells?dataset=VOLVE&limit=50")
        assert resp.status_code == 200
        for w in resp.json()["wells"]:
            assert w["dataset"] == "VOLVE"

    def test_get_well(self, client):
        resp = client.get("/wells/lookup", params={"dataset": "VOLVE", "well_id": "15/9-F-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["well_id"] == "15/9-F-1"
        assert data["has_coordinates"] is True

    def test_get_well_not_found(self, client):
        resp = client.get("/wells/lookup", params={"dataset": "VOLVE", "well_id": "NONEXISTENT"})
        assert resp.status_code == 404

    def test_nearby(self, client):
        resp = client.get("/wells/nearby", params={"dataset": "VOLVE", "well_id": "15/9-F-1", "radius_km": 50, "limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reference_well"] == "15/9-F-1"
        assert data["radius_km"] == 50.0
        for r in data["results"]:
            assert r["distance_km"] <= 50.0
            assert r["rank"] > 0

    def test_similar(self, client):
        resp = client.get("/wells/similar", params={"dataset": "VOLVE", "well_id": "15/9-F-1", "top_k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reference_well"] == "15/9-F-1"
        assert len(data["results"]) <= 5

    def test_context(self, client):
        resp = client.get("/wells/context", params={"dataset": "VOLVE", "well_id": "15/9-F-1", "nearby_limit": 3, "similar_limit": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["well_id"] == "15/9-F-1"
        assert "nearby_wells" in data
        assert "similar_wells" in data
        assert data["nearby_well_count"] == len(data["nearby_wells"])
        assert data["similar_well_count"] == len(data["similar_wells"])

    def test_well_state(self, client):
        resp = client.get("/wells/state", params={"dataset": "VOLVE", "well_id": "15/9-F-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["well_id"] == "15/9-F-1"
        assert data["is_simulated"] is False
