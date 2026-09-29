"""
Tests for the retrieval library (retrieval/). These are integration tests
against the real geointelligence.window_embeddings / .well_embeddings
tables in PostgreSQL - no mocks - since the point is to validate the
actual deterministic retrieval behavior against real loaded data.

Run with: venv/bin/python -m pytest tests/test_retrieval.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import retrieval as r


# ============================================================
# FIXTURES: real keys pulled from the database once per session
# ============================================================

@pytest.fixture(scope="module")
def conn():
    connection = r.get_connection()
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def force_window_key(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT dataset, well_id, window_id FROM geointelligence.window_embeddings "
            "WHERE dataset = 'FORCE_2020' ORDER BY id LIMIT 1;"
        )
        return cur.fetchone()


@pytest.fixture(scope="module")
def volve_window_key(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT dataset, well_id, window_id FROM geointelligence.window_embeddings "
            "WHERE dataset = 'VOLVE' ORDER BY id LIMIT 1;"
        )
        return cur.fetchone()


@pytest.fixture(scope="module")
def force_well_key(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT dataset, well_id FROM geointelligence.well_embeddings "
            "WHERE dataset = 'FORCE_2020' ORDER BY id LIMIT 1;"
        )
        return cur.fetchone()


@pytest.fixture(scope="module")
def volve_well_key(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT dataset, well_id FROM geointelligence.well_embeddings "
            "WHERE dataset = 'VOLVE' ORDER BY id LIMIT 1;"
        )
        return cur.fetchone()


@pytest.fixture(scope="module")
def force_query_vector(force_window_key):
    dataset, well_id, window_id = force_window_key
    return r.fetch_window_vector(dataset, well_id, window_id)


# ============================================================
# 1. WINDOW SEARCH
# ============================================================

def test_window_search_returns_results(force_query_vector):
    results = r.search_similar_windows(force_query_vector, top_k=10)
    assert len(results) > 0
    assert all(isinstance(res, r.WindowResult) for res in results)
    assert [res.rank for res in results] == list(range(1, len(results) + 1))


def test_window_search_similarity_descending(force_query_vector):
    results = r.search_similar_windows(force_query_vector, top_k=15)
    similarities = [res.similarity for res in results]
    assert similarities == sorted(similarities, reverse=True)


# ============================================================
# 2. WELL SEARCH
# ============================================================

def test_well_search_returns_results(force_query_vector):
    results = r.search_similar_wells(force_query_vector, top_k=10)
    assert len(results) > 0
    assert all(isinstance(res, r.WellResult) for res in results)
    assert [res.rank for res in results] == list(range(1, len(results) + 1))


# ============================================================
# 3. TOP_K BEHAVIOR
# ============================================================

def test_top_k_behavior(force_query_vector):
    results_3 = r.search_similar_windows(force_query_vector, top_k=3)
    results_7 = r.search_similar_windows(force_query_vector, top_k=7)
    assert len(results_3) == 3
    assert len(results_7) == 7
    # the smaller result set must be a prefix of the larger one (same order)
    assert [res.window_id for res in results_3] == [res.window_id for res in results_7[:3]]


# ============================================================
# 4. DATASET FILTERING
# ============================================================

def test_dataset_filter(force_query_vector):
    results = r.search_similar_windows(force_query_vector, top_k=20, dataset="VOLVE")
    assert len(results) > 0
    assert all(res.dataset == "VOLVE" for res in results)


# ============================================================
# 5. WELL FILTERING
# ============================================================

def test_well_filter(force_window_key, force_query_vector):
    _, well_id, _ = force_window_key
    results = r.search_similar_windows(force_query_vector, top_k=50, well_id=well_id)
    assert len(results) > 0
    assert all(res.well_id == well_id for res in results)


# ============================================================
# 6. CURVES_PRESENT FILTERING
# ============================================================

def test_curves_present_filter(force_query_vector):
    threshold = 8
    results = r.search_similar_windows(force_query_vector, top_k=20, min_curves_present=threshold)
    assert len(results) > 0
    assert all(res.curves_present >= threshold for res in results)


# ============================================================
# 7. SELF-RESULT EXCLUSION
# ============================================================

def test_self_exclusion_window(force_window_key):
    dataset, well_id, window_id = force_window_key
    results = r.search_similar_windows_by_id(dataset, well_id, window_id, top_k=20)
    assert not any(
        (res.dataset, res.well_id, res.window_id) == (dataset, well_id, window_id)
        for res in results
    )


def test_self_exclusion_well(force_well_key):
    dataset, well_id = force_well_key
    results = r.search_similar_wells_by_id(dataset, well_id, top_k=20)
    assert not any((res.dataset, res.well_id) == (dataset, well_id) for res in results)


# ============================================================
# 8. DETERMINISTIC ORDERING
# ============================================================

def test_deterministic_ordering(force_query_vector):
    first = r.search_similar_windows(force_query_vector, top_k=10)
    second = r.search_similar_windows(force_query_vector, top_k=10)
    key = lambda res: (res.dataset, res.well_id, res.window_id, round(res.similarity, 10))
    assert [key(res) for res in first] == [key(res) for res in second]


# ============================================================
# 9. EMPTY-RESULT HANDLING
# ============================================================

def test_empty_result_handling(force_query_vector):
    results = r.search_similar_windows(
        force_query_vector, top_k=10, well_id="__no_such_well_id__"
    )
    assert results == []


def test_empty_result_handling_impossible_curves_present(force_query_vector):
    results = r.search_similar_windows(force_query_vector, top_k=10, min_curves_present=9999)
    assert results == []


# ============================================================
# 10. INVALID VECTOR DIMENSION HANDLING
# ============================================================

def test_invalid_vector_dimension_too_short():
    with pytest.raises(r.InvalidVectorDimensionError):
        r.search_similar_windows([0.0] * 5, top_k=5)


def test_invalid_vector_dimension_too_long():
    expected_dim = r.get_embedding_dimension()
    with pytest.raises(r.InvalidVectorDimensionError):
        r.search_similar_wells([0.0] * (expected_dim + 5), top_k=5)


# ============================================================
# BONUS: cross-dataset query-by-example sanity (Volve -> FORCE/VOLVE)
# ============================================================

def test_query_by_example_volve_window(volve_window_key):
    dataset, well_id, window_id = volve_window_key
    results = r.search_similar_windows_by_id(dataset, well_id, window_id, top_k=5)
    assert len(results) == 5
    assert not any(
        (res.dataset, res.well_id, res.window_id) == (dataset, well_id, window_id)
        for res in results
    )


def test_query_by_example_volve_well(volve_well_key):
    dataset, well_id = volve_well_key
    results = r.search_similar_wells_by_id(dataset, well_id, top_k=5)
    assert len(results) == 5
    assert not any((res.dataset, res.well_id) == (dataset, well_id) for res in results)
