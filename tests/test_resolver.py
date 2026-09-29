"""
Tests for the query resolver (resolver/).

Unit tests use mocks for database and retrieval dependencies.
Integration tests (marked with @pytest.mark.integration) hit the real
PostgreSQL database and are skipped if it's not available.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query import StructuredQuery, validate_query
from resolver import (
    QueryResolver,
    ResolutionResult,
    EntityNotFoundError,
    ResolverDataError,
)


# ============================================================
# Helpers
# ============================================================

def _mock_well_result(dataset="VOLVE", well_id="15/9-F-4", similarity=0.92, rank=1):
    r = MagicMock()
    r.dataset = dataset
    r.well_id = well_id
    r.similarity = similarity
    r.rank = rank
    r.windows_total = 100
    r.windows_pooled = 90
    r.windows_excluded = 10
    r.pooling_fraction = 0.9
    return r


def _mock_window_result(dataset="FORCE_2020", well_id="34/6-1", window_id=5,
                         similarity=0.88, rank=1):
    r = MagicMock()
    r.dataset = dataset
    r.well_id = well_id
    r.window_id = window_id
    r.depth_start_m = 1000.0
    r.depth_end_m = 1020.0
    r.similarity = similarity
    r.rank = rank
    r.curves_present = 8
    return r


def _make_resolver_with_mocks():
    resolver = QueryResolver.__new__(QueryResolver)
    resolver._conn = MagicMock()
    resolver._conn.closed = False
    return resolver


# ============================================================
# 1. similar_wells
# ============================================================

@patch("resolver.resolver.search_similar_wells_by_id")
def test_similar_wells_basic(mock_search):
    mock_search.return_value = [
        _mock_well_result("VOLVE", "15/9-F-4", 0.95, 1),
        _mock_well_result("FORCE_2020", "34/6-1", 0.88, 2),
    ]
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=None)

    q = validate_query({
        "intent": "similar_wells", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1", "top_k": 5,
    })
    result = resolver.resolve(q)

    assert result.intent == "similar_wells"
    assert result.status == "success"
    assert result.result_count == 2
    assert len(result.results) == 2
    assert result.results[0]["well_id"] == "15/9-F-4"
    assert result.results[0]["similarity"] == 0.95
    assert result.metadata["query_well"]["well_id"] == "15/9-F-1"
    mock_search.assert_called_once()


@patch("resolver.resolver.search_similar_wells_by_id")
def test_similar_wells_with_dataset_filter(mock_search):
    mock_search.return_value = [_mock_well_result("FORCE_2020", "34/6-1", 0.85, 1)]
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=None)

    q = validate_query({
        "intent": "similar_wells", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1", "dataset_filter": "FORCE_2020", "top_k": 3,
    })
    result = resolver.resolve(q)

    assert result.result_count == 1
    assert result.results[0]["dataset"] == "FORCE_2020"
    call_kwargs = mock_search.call_args
    assert call_kwargs.kwargs.get("dataset_filter") == "FORCE_2020" or \
           (len(call_kwargs.args) > 3 and call_kwargs.args[3] == "FORCE_2020")


@patch("resolver.resolver.search_similar_wells_by_id")
def test_similar_wells_empty_results(mock_search):
    mock_search.return_value = []
    resolver = _make_resolver_with_mocks()

    q = validate_query({
        "intent": "similar_wells", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
    })
    result = resolver.resolve(q)

    assert result.status == "success"
    assert result.result_count == 0
    assert result.results == []


@patch("resolver.resolver.search_similar_wells_by_id")
def test_similar_wells_query_well_excluded(mock_search):
    mock_search.return_value = [_mock_well_result("VOLVE", "15/9-F-4", 0.9, 1)]
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=None)

    q = validate_query({
        "intent": "similar_wells", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1", "top_k": 5,
    })
    result = resolver.resolve(q)

    for r in result.results:
        assert not (r["dataset"] == "VOLVE" and r["well_id"] == "15/9-F-1")


# ============================================================
# 2. similar_windows
# ============================================================

@patch("resolver.resolver.search_similar_windows_by_id")
def test_similar_windows_basic(mock_search):
    mock_search.return_value = [
        _mock_window_result("FORCE_2020", "34/6-1", 10, 0.91, 1),
        _mock_window_result("VOLVE", "15/9-F-4", 3, 0.85, 2),
    ]
    resolver = _make_resolver_with_mocks()

    q = validate_query({
        "intent": "similar_windows", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1", "target_window_id": 5, "top_k": 10,
    })
    result = resolver.resolve(q)

    assert result.intent == "similar_windows"
    assert result.result_count == 2
    assert result.results[0]["window_id"] == 10
    assert result.results[0]["similarity"] == 0.91
    assert result.metadata["query_window"]["window_id"] == 5


@patch("resolver.resolver.search_similar_windows_by_id")
def test_similar_windows_with_min_curves(mock_search):
    mock_search.return_value = [_mock_window_result()]
    resolver = _make_resolver_with_mocks()

    q = validate_query({
        "intent": "similar_windows", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1", "target_window_id": 5,
        "min_curves_present": 6,
    })
    result = resolver.resolve(q)

    assert result.status == "success"
    call_kwargs = mock_search.call_args
    assert call_kwargs.kwargs.get("min_curves_present") == 6 or \
           any(v == 6 for v in call_kwargs.args)


# ============================================================
# 3. well_information
# ============================================================

def test_well_information_with_sodir_link():
    resolver = _make_resolver_with_mocks()

    from resolver.models import WellInfo, CompanyRole
    mock_info = WellInfo(
        dataset="VOLVE", well_id="15/9-F-1", source_system="SODIR",
        sodir_wellbore_id=12345, sodir_wellbore_name="15/9-F-1",
        field_name="VOLVE", operator="Equinor", match_method="exact",
        companies=[CompanyRole(company_name="Equinor", role="OPERATOR")],
    )
    resolver._fetch_well_info = MagicMock(return_value=mock_info)

    q = validate_query({
        "intent": "well_information", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
    })
    result = resolver.resolve(q)

    assert result.intent == "well_information"
    assert result.status == "success"
    assert result.results["well_id"] == "15/9-F-1"
    assert result.results["field_name"] == "VOLVE"
    assert result.results["sodir_wellbore_id"] == 12345
    assert "SODIR" in result.sources
    assert result.metadata["sodir_linked"] is True


def test_well_information_no_sodir_link():
    resolver = _make_resolver_with_mocks()

    from resolver.models import WellInfo
    mock_info = WellInfo(
        dataset="FORCE_2020", well_id="UNKNOWN-WELL", source_system="FORCE_2020",
    )
    resolver._fetch_well_info = MagicMock(return_value=mock_info)

    q = validate_query({
        "intent": "well_information", "target_dataset": "FORCE_2020",
        "target_well_id": "UNKNOWN-WELL",
    })
    result = resolver.resolve(q)

    assert result.status == "partial"
    assert result.results["sodir_wellbore_id"] is None
    assert result.metadata["sodir_linked"] is False


# ============================================================
# 4. formation_information
# ============================================================

def test_formation_information_found():
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=12345)

    from resolver.models import FormationTop
    mock_tops = [
        FormationTop(formation_name="UTSIRA", formation_id=1, top_depth_m=800.0),
        FormationTop(formation_name="HORDALAND", formation_id=2, top_depth_m=1200.0,
                     base_depth_m=1500.0, parent_formation_name="ROGALAND GP"),
    ]
    resolver._fetch_formation_tops = MagicMock(return_value=mock_tops)

    q = validate_query({
        "intent": "formation_information", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
    })
    result = resolver.resolve(q)

    assert result.intent == "formation_information"
    assert result.status == "success"
    assert result.result_count == 2
    assert result.results[0]["formation_name"] == "UTSIRA"
    assert result.results[1]["base_depth_m"] == 1500.0
    assert "SODIR" in result.sources


def test_formation_information_no_sodir_link():
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=None)

    q = validate_query({
        "intent": "formation_information", "target_dataset": "FORCE_2020",
        "target_well_id": "UNKNOWN-WELL",
    })
    result = resolver.resolve(q)

    assert result.status == "not_found"
    assert result.result_count == 0
    assert "No SODIR identity link" in result.metadata.get("reason", "")


# ============================================================
# 5. compare_wells
# ============================================================

@patch("resolver.resolver.fetch_well_vector")
def test_compare_wells_basic(mock_fetch_vec):
    resolver = _make_resolver_with_mocks()

    from resolver.models import WellInfo
    info1 = WellInfo(dataset="VOLVE", well_id="15/9-19 A", source_system="SODIR",
                     sodir_wellbore_id=100, field_name="VOLVE")
    info2 = WellInfo(dataset="VOLVE", well_id="15/9-19 SR", source_system="SODIR",
                     sodir_wellbore_id=200, field_name="VOLVE")
    resolver._fetch_well_info = MagicMock(side_effect=[info1, info2])

    mock_fetch_vec.side_effect = [[0.5] * 30, [0.5] * 30]

    q = validate_query({
        "intent": "compare_wells", "target_dataset": "VOLVE",
        "target_well_id": "15/9-19 A", "comparison_dataset": "VOLVE",
        "comparison_well_id": "15/9-19 SR",
    })
    result = resolver.resolve(q)

    assert result.intent == "compare_wells"
    assert result.status == "success"
    assert result.results["target"]["well_id"] == "15/9-19 A"
    assert result.results["comparison"]["well_id"] == "15/9-19 SR"
    assert result.results["similarity"] is not None
    assert result.results["similarity"] == pytest.approx(1.0)
    assert result.result_count == 2


@patch("resolver.resolver.fetch_well_vector")
def test_compare_wells_no_embeddings(mock_fetch_vec):
    resolver = _make_resolver_with_mocks()

    from resolver.models import WellInfo
    info1 = WellInfo(dataset="VOLVE", well_id="15/9-19 A", source_system="VOLVE")
    info2 = WellInfo(dataset="VOLVE", well_id="15/9-19 SR", source_system="VOLVE")
    resolver._fetch_well_info = MagicMock(side_effect=[info1, info2])

    mock_fetch_vec.side_effect = LookupError("no embedding")

    q = validate_query({
        "intent": "compare_wells", "target_dataset": "VOLVE",
        "target_well_id": "15/9-19 A", "comparison_dataset": "VOLVE",
        "comparison_well_id": "15/9-19 SR",
    })
    result = resolver.resolve(q)

    assert result.results["similarity"] is None


# ============================================================
# 6. geological_context
# ============================================================

def test_geological_context_found():
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=12345)

    from resolver.models import GeologicalContextGroup
    mock_groups = [
        GeologicalContextGroup(entity_type="field", records=[
            {"field_id": 1, "field_name": "VOLVE", "operator": "Equinor"}
        ], record_count=1),
        GeologicalContextGroup(entity_type="company", records=[
            {"company_name": "Equinor", "role": "OPERATOR"}
        ], record_count=1),
    ]
    resolver._fetch_geological_context = MagicMock(return_value=mock_groups)

    q = validate_query({
        "intent": "geological_context", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-4",
        "requested_geological_context": ["field", "company"],
    })
    result = resolver.resolve(q)

    assert result.intent == "geological_context"
    assert result.status == "success"
    assert result.result_count == 2
    assert len(result.results) == 2
    assert result.results[0]["entity_type"] == "field"
    assert "SODIR" in result.sources


def test_geological_context_no_sodir_link():
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=None)

    q = validate_query({
        "intent": "geological_context", "target_dataset": "FORCE_2020",
        "target_well_id": "NO-LINK-WELL",
    })
    result = resolver.resolve(q)

    assert result.status == "not_found"
    assert result.result_count == 0


def test_geological_context_defaults_to_common_entities():
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=12345)

    from resolver.models import GeologicalContextGroup
    resolver._fetch_geological_context = MagicMock(return_value=[
        GeologicalContextGroup(entity_type="field", records=[], record_count=0),
    ])

    q = validate_query({
        "intent": "geological_context", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
    })
    result = resolver.resolve(q)

    call_args = resolver._fetch_geological_context.call_args
    requested = call_args[0][1]
    assert "field" in requested
    assert "formations" in requested


# ============================================================
# Error handling
# ============================================================

@patch("resolver.resolver.search_similar_wells_by_id")
def test_unknown_well_raises_entity_not_found(mock_search):
    mock_search.side_effect = LookupError("No well embedding found for dataset='VOLVE', well_id='NONEXISTENT'")
    resolver = _make_resolver_with_mocks()

    q = validate_query({
        "intent": "similar_wells", "target_dataset": "VOLVE",
        "target_well_id": "NONEXISTENT",
    })
    with pytest.raises(EntityNotFoundError):
        resolver.resolve(q)


# ============================================================
# Provenance preservation
# ============================================================

@patch("resolver.resolver.search_similar_wells_by_id")
def test_provenance_preserved_in_results(mock_search):
    mock_search.return_value = [
        _mock_well_result("VOLVE", "15/9-F-4", 0.95, 1),
        _mock_well_result("FORCE_2020", "34/6-1", 0.88, 2),
    ]
    resolver = _make_resolver_with_mocks()
    resolver._resolve_wellbore_id = MagicMock(return_value=None)

    q = validate_query({
        "intent": "similar_wells", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
    })
    result = resolver.resolve(q)

    assert result.results[0]["dataset"] == "VOLVE"
    assert result.results[1]["dataset"] == "FORCE_2020"
    assert sorted(result.sources) == ["FORCE_2020", "VOLVE"]


# ============================================================
# Top-k behavior
# ============================================================

@patch("resolver.resolver.search_similar_wells_by_id")
def test_top_k_default(mock_search):
    mock_search.return_value = []
    resolver = _make_resolver_with_mocks()

    q = validate_query({
        "intent": "similar_wells", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
    })
    resolver.resolve(q)

    call_kwargs = mock_search.call_args
    assert call_kwargs.kwargs.get("top_k") == 10 or call_kwargs.args[2] == 10


# ============================================================
# Integration tests (require real PostgreSQL)
# ============================================================

def _db_available():
    try:
        from retrieval.vector_search import get_connection
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_integration_similar_wells():
    with QueryResolver() as resolver:
        q = validate_query({
            "intent": "similar_wells", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1", "top_k": 3,
        })
        result = resolver.resolve(q)
        assert result.status == "success"
        assert result.result_count > 0
        assert result.result_count <= 3
        for r in result.results:
            assert "dataset" in r
            assert "well_id" in r
            assert "similarity" in r
            assert not (r["dataset"] == "VOLVE" and r["well_id"] == "15/9-F-1")


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_integration_similar_windows():
    with QueryResolver() as resolver:
        q = validate_query({
            "intent": "similar_windows", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1", "target_window_id": 11, "top_k": 3,
        })
        result = resolver.resolve(q)
        assert result.status == "success"
        assert result.result_count <= 3
        for r in result.results:
            assert "window_id" in r


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_integration_well_information():
    with QueryResolver() as resolver:
        q = validate_query({
            "intent": "well_information", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1",
        })
        result = resolver.resolve(q)
        assert result.status in ("success", "partial")
        assert result.results["well_id"] == "15/9-F-1"


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_integration_formation_information():
    with QueryResolver() as resolver:
        q = validate_query({
            "intent": "formation_information", "target_dataset": "VOLVE",
            "target_well_id": "15/9-19 SR",
        })
        result = resolver.resolve(q)
        assert result.status in ("success", "not_found")
        if result.status == "success":
            assert result.result_count > 0
            assert "formation_name" in result.results[0]


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_integration_compare_wells():
    with QueryResolver() as resolver:
        q = validate_query({
            "intent": "compare_wells", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1", "comparison_dataset": "VOLVE",
            "comparison_well_id": "15/9-F-4",
        })
        result = resolver.resolve(q)
        assert result.status == "success"
        assert result.results["target"]["well_id"] == "15/9-F-1"
        assert result.results["comparison"]["well_id"] == "15/9-F-4"


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_integration_geological_context():
    with QueryResolver() as resolver:
        q = validate_query({
            "intent": "geological_context", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1",
            "requested_geological_context": ["field", "company", "formations"],
        })
        result = resolver.resolve(q)
        assert result.status in ("success", "not_found")
        if result.status == "success":
            entity_types = [g["entity_type"] for g in result.results]
            assert "field" in entity_types or "company" in entity_types
