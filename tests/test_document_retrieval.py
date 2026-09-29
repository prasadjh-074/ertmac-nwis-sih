"""
Tests for document_retrieval/ (query-time semantic search over ingested
document chunks - the 384-dim sentence-transformer space, kept completely
separate from the 30-dim well/window embedding space in retrieval/).

Unit tests exercise filters/ranking with no database. Integration tests
hit the real geo_intelligence database and are skipped when unavailable.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from document_retrieval.filters import DocumentFilters, build_where_clause
from document_retrieval.models import DocumentSearchResult
from document_retrieval.ranking import rank_document_rows


# ============================================================
# Filters (no database required)
# ============================================================

class TestDocumentFilters:
    def test_no_filters_produces_no_clauses(self):
        clauses, params = DocumentFilters().to_sql()
        assert clauses == []
        assert params == []

    def test_source_type_filter(self):
        clauses, params = DocumentFilters(source_type="pdf").to_sql()
        assert clauses == ["d.source_type = %s"]
        assert params == ["pdf"]

    def test_file_name_filter(self):
        clauses, params = DocumentFilters(file_name="report.pdf").to_sql()
        assert clauses == ["d.file_name = %s"]
        assert params == ["report.pdf"]

    def test_both_filters_combine(self):
        clauses, params = DocumentFilters(source_type="text", file_name="a.txt").to_sql()
        assert len(clauses) == 2
        assert params == ["text", "a.txt"]

    def test_build_where_clause_empty(self):
        assert build_where_clause([]) == ""

    def test_build_where_clause_joins_with_and(self):
        sql = build_where_clause(["a = %s", "b = %s"])
        assert sql == "WHERE a = %s AND b = %s"


# ============================================================
# Ranking (no database required)
# ============================================================

class TestDocumentRanking:
    def test_rank_assigns_1_indexed_rank(self):
        rows = [
            ("id1", "doc1", "file.txt", 1, 0, None, "text one", 0.1),
            ("id2", "doc1", "file.txt", 1, 1, "SECTION", "text two", 0.3),
        ]
        results = rank_document_rows(rows)
        assert [r.rank for r in results] == [1, 2]

    def test_rank_converts_distance_to_similarity(self):
        rows = [("id1", "doc1", "file.txt", 1, 0, None, "text", 0.25)]
        results = rank_document_rows(rows)
        assert results[0].similarity == pytest.approx(0.75)

    def test_rank_preserves_all_fields(self):
        rows = [("id1", "doc1", "file.txt", 3, 2, "FORMATION TOPS", "some text", 0.4)]
        results = rank_document_rows(rows)
        r = results[0]
        assert r.chunk_id == "id1"
        assert r.document_id == "doc1"
        assert r.file_name == "file.txt"
        assert r.page_number == 3
        assert r.chunk_index == 2
        assert r.section == "FORMATION TOPS"
        assert r.text == "some text"

    def test_empty_rows_returns_empty_list(self):
        assert rank_document_rows([]) == []

    def test_returns_document_search_result_instances(self):
        rows = [("id1", "doc1", "file.txt", 1, 0, None, "text", 0.1)]
        results = rank_document_rows(rows)
        assert isinstance(results[0], DocumentSearchResult)


# ============================================================
# Integration: real database, real sentence-transformer model
# ============================================================

def _db_available():
    try:
        from document_retrieval.search import get_connection
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
class TestDocumentSearchIntegration:
    def test_search_returns_results_for_real_query(self):
        from document_retrieval.search import search_documents

        results = search_documents("formation tops in a well report", top_k=5)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, DocumentSearchResult)
            assert 0 <= r.similarity <= 1.0

    def test_search_respects_top_k(self):
        from document_retrieval.search import search_documents

        results = search_documents("well information", top_k=1)
        assert len(results) <= 1

    def test_search_results_ranked_by_similarity_descending(self):
        from document_retrieval.search import search_documents

        results = search_documents("well formation report", top_k=10)
        sims = [r.similarity for r in results]
        assert sims == sorted(sims, reverse=True)

    def test_embed_query_produces_384_dim_vector(self):
        from document_retrieval.search import embed_query

        vec = embed_query("test query")
        assert len(vec) == 384

    def test_search_with_precomputed_embedding(self):
        from document_retrieval.search import embed_query, search_documents

        vec = embed_query("formation tops")
        results = search_documents("formation tops", top_k=3, query_embedding=vec)
        assert isinstance(results, list)

    def test_invalid_embedding_dimension_rejected(self):
        from document_retrieval.search import search_documents

        with pytest.raises(ValueError):
            search_documents("x", query_embedding=[0.1, 0.2, 0.3])
