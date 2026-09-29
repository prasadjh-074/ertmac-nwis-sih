"""Tests for the FastAPI backend.

Two groups:

  * **unit-style** tests use FastAPI's dependency_overrides to inject
    fake connections / a fake graph runner.  They require no database
    and no network — they exercise middleware, error envelopes,
    schema validation, and endpoint wiring in isolation.
  * **integration** tests (@pytest.mark.integration) hit the real
    PostgreSQL DB, in the same style as the existing
    tests/test_nearby.py::TestAPIIntegration group.  They validate
    that the router refactor preserves every legacy endpoint's
    contract on a live database.

Existing @pytest.mark.integration tests in test_nearby.py already
cover the 8 legacy /health and /wells endpoints; here we focus on
the middleware, error handlers, and the newly added /query,
/events, /risk, /documents routers.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient


REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$|^[A-Za-z0-9\-]{6,}$")


# ── Fixtures ───────────────────────────────────────────────────

class _FakeCursor:
    """Minimal cursor that yields deterministic rows for the endpoints
    under test.  A single instance is reused per fixture to keep the
    test state small; individual tests set rows via .set_rows()."""

    def __init__(self):
        self._rows: list = []
        self.last_sql: str | None = None
        self.last_params = None

    def set_rows(self, rows):
        self._rows = list(rows)

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        out, self._rows = self._rows, []
        return out


class _FakeConn:
    def __init__(self):
        self._cursor = _FakeCursor()
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def fake_conn():
    return _FakeConn()


@pytest.fixture
def client(fake_conn):
    """A TestClient with the DB dependency stubbed to fake_conn.

    Uses TestClient as a context manager so the lifespan runs — the
    lifespan safely degrades when the DB isn't reachable (which is
    fine here since we override get_conn anyway).
    """
    from api.app import app
    from api.deps import get_conn

    def _override():
        yield fake_conn

    app.dependency_overrides[get_conn] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Middleware ────────────────────────────────────────────────

class TestMiddleware:
    def test_generates_request_id_when_missing(self, client, fake_conn):
        fake_conn.cursor().set_rows([(1,)])
        resp = client.get("/health")
        assert resp.status_code == 200
        rid = resp.headers.get("X-Request-ID")
        assert rid is not None
        assert REQUEST_ID_RE.match(rid)

    def test_forwards_client_request_id(self, client, fake_conn):
        fake_conn.cursor().set_rows([(1,)])
        resp = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
        assert resp.headers["X-Request-ID"] == "trace-abc-123"

    def test_returns_elapsed_ms_header(self, client, fake_conn):
        fake_conn.cursor().set_rows([(1,)])
        resp = client.get("/health")
        assert resp.status_code == 200
        elapsed = resp.headers.get("X-Elapsed-Ms")
        assert elapsed is not None
        assert float(elapsed) >= 0.0


# ── Error handlers ────────────────────────────────────────────

class TestErrorHandlers:
    def test_404_returns_structured_envelope(self, client):
        resp = client.get("/wells/lookup", params={"dataset": "VOLVE", "well_id": "MISSING"})
        # The endpoint's own 404 (well not found) surfaces here — the
        # fake conn returns no rows for get_well_location.
        body = resp.json()
        assert "error" in body
        e = body["error"]
        assert e["type"] == "not_found"
        assert e["status"] == 404
        assert e["request_id"] is not None
        assert "message" in e

    def test_422_validation_error_shape(self, client):
        # top_k over the allowed maximum → 422
        resp = client.post(
            "/documents/search",
            json={"query": "loss", "top_k": 999},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["type"] == "validation_error"
        assert isinstance(body["error"]["detail"], list)

    def test_400_bad_uuid(self, client):
        resp = client.get("/documents/not-a-uuid")
        assert resp.status_code == 400
        assert resp.json()["error"]["type"] == "bad_request"

    def test_health_ok_with_db(self, client, fake_conn):
        fake_conn.cursor().set_rows([(1,)])
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"


# ── /query endpoints ──────────────────────────────────────────

class TestQueryRouter:
    def test_natural_language_503_when_llm_disabled(self, client):
        from api.app import app
        from api.deps import get_graph_runner

        # Force "no runner" regardless of the ambient GROQ_API_KEY —
        # the endpoint contract we're testing is: no runner → 503.
        app.dependency_overrides[get_graph_runner] = lambda: None
        try:
            resp = client.post("/query", json={"question": "hello"})
        finally:
            app.dependency_overrides.pop(get_graph_runner, None)
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["type"] == "service_unavailable"

    def test_natural_language_uses_runner_when_available(self, client):
        from api.app import app
        from api.deps import get_graph_runner
        from graph.state import (
            ConfidenceScore, EvidenceItem, ExecutionMetadata, QueryResponse,
        )

        class _FakeRunner:
            def run_query(self, question):
                return QueryResponse(
                    answer=f"echo:{question}",
                    structured_query={"intent": "similar_wells"},
                    evidence=[EvidenceItem(source_system="VOLVE", entity_type="well", well_id="15/9-F-1")],
                    confidence_score=ConfidenceScore(value=0.7, label="MEDIUM", basis=["proximity"]),
                    rationale=["ranked by cosine"],
                    provenance=["VOLVE"],
                    metadata=ExecutionMetadata(intent="similar_wells", llm_used=True),
                    errors=[],
                )

        app.dependency_overrides[get_graph_runner] = lambda: _FakeRunner()
        try:
            resp = client.post("/query", json={"question": "similar wells to 15/9-F-1"})
        finally:
            app.dependency_overrides.pop(get_graph_runner, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "echo:similar wells to 15/9-F-1"
        assert body["structured_query"]["intent"] == "similar_wells"
        assert body["confidence_score"]["is_probability"] is False
        assert body["metadata"]["llm_used"] is True

    def test_natural_language_validation_rejects_empty(self, client):
        resp = client.post("/query", json={"question": ""})
        assert resp.status_code == 422

    def test_structured_validation_rejects_extra_field(self, client):
        resp = client.post(
            "/query/structured",
            json={"structured_query": {"intent": "similar_wells", "not_a_real_field": 1}},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["type"] == "validation_error"

    def test_structured_validation_rejects_bad_intent(self, client):
        resp = client.post(
            "/query/structured",
            json={"structured_query": {"intent": "select * from wells"}},
        )
        assert resp.status_code == 422


# ── /events endpoints ──────────────────────────────────────────

class TestEventsRouter:
    def test_events_well_invalid_event_type(self, client):
        resp = client.get(
            "/events/well",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1", "event_type": "not_a_type"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["type"] == "bad_request"

    def test_events_near_depth_negative_depth_rejected(self, client):
        resp = client.get(
            "/events/near-depth",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1", "depth_m": -10},
        )
        assert resp.status_code == 422

    def test_events_correlated_bad_radius_rejected(self, client):
        resp = client.get(
            "/events/correlated",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1", "radius_km": 0},
        )
        assert resp.status_code == 422

    def test_events_well_empty_result(self, client, fake_conn, monkeypatch):
        # Stub events.storage.load_events_for_well to return []
        import api.routers.events as events_router

        def _empty(**kwargs):
            return []

        monkeypatch.setattr(events_router, "load_events_for_well", _empty)
        resp = client.get(
            "/events/well",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["events"] == []

    def test_events_well_serialises_events(self, client, monkeypatch):
        import api.routers.events as events_router
        from events.models import (
            DrillingEvent, EventProvenance, EventSeverity, EventType,
        )

        ev = DrillingEvent(
            event_type=EventType.MUD_LOSS,
            severity=EventSeverity.MEDIUM,
            description="losses at 3200m",
            depth_start_m=3200.0,
            formation="Draupne",
            well_id="15/9-F-1",
            dataset="VOLVE",
            provenance=EventProvenance(
                source_type="sodir_history",
                source_table="subsurface.wellbore_history",
                extraction_method="regex_keyword",
                extraction_confidence=0.9,
                raw_text_snippet="losses at 3200m",
            ),
        )

        monkeypatch.setattr(events_router, "load_events_for_well",
                            lambda **kwargs: [ev])
        resp = client.get(
            "/events/well",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        e = body["events"][0]
        assert e["event_type"] == "mud_loss"
        assert e["depth_start_m"] == 3200.0
        assert e["formation"] == "Draupne"
        assert e["provenance"]["source_table"] == "subsurface.wellbore_history"
        assert e["provenance"]["extraction_method"] == "regex_keyword"


# ── /risk endpoints ──────────────────────────────────────────

class TestRiskRouter:
    def test_risk_assess_no_events_returns_all_five(self, client, monkeypatch):
        import api.routers.risk as risk_router

        monkeypatch.setattr(risk_router, "correlate_historical_events",
                            lambda **kwargs: [])
        # Force the "gather_well_evidence" branch to be skipped.
        monkeypatch.setattr(risk_router, "_gather_well_evidence_safe",
                            lambda *a, **k: None)

        resp = client.get(
            "/risk/assess",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["correlated_event_count"] == 0
        assert len(body["assessments"]) == 5
        types = {a["risk_type"] for a in body["assessments"]}
        assert types == {
            "mud_loss_risk", "stuck_pipe_risk", "kick_overpressure_risk",
            "torque_spike_risk", "cementing_risk",
        }
        for a in body["assessments"]:
            assert a["level"] == "low"
            assert a["methodology"] == "evidence_rule_based"
            assert isinstance(a["limitations"], list) and len(a["limitations"]) >= 1

    def test_risk_assess_scores_are_never_probabilities(self, client, monkeypatch):
        import api.routers.risk as risk_router

        monkeypatch.setattr(risk_router, "correlate_historical_events",
                            lambda **kwargs: [])
        monkeypatch.setattr(risk_router, "_gather_well_evidence_safe",
                            lambda *a, **k: None)

        resp = client.get(
            "/risk/assess",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1"},
        )
        for a in resp.json()["assessments"]:
            assert 0.0 <= a["score"] <= 1.0
            assert a["model_or_rule_source"] == "evidence_rule_based"

    def test_risk_alerts_no_correlation_returns_empty(self, client, monkeypatch):
        import api.routers.risk as risk_router

        monkeypatch.setattr(risk_router, "correlate_historical_events",
                            lambda **kwargs: [])
        monkeypatch.setattr(risk_router, "_gather_well_evidence_safe",
                            lambda *a, **k: None)

        resp = client.get(
            "/risk/alerts",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["alerts"] == []


# ── /documents endpoints ─────────────────────────────────────

class TestDocumentsRouter:
    def test_documents_search_400_on_bad_query_embedding(self, client, monkeypatch):
        import api.routers.documents as docs_router

        def _bad(**kwargs):
            raise ValueError("Query embedding has 5 dimensions, expected 384")

        monkeypatch.setattr(docs_router, "search_documents", _bad)
        resp = client.post("/documents/search", json={"query": "loss", "top_k": 3})
        assert resp.status_code == 400
        assert resp.json()["error"]["type"] == "bad_request"

    def test_documents_search_empty_result(self, client, monkeypatch):
        import api.routers.documents as docs_router
        monkeypatch.setattr(docs_router, "search_documents", lambda **k: [])

        resp = client.post("/documents/search", json={"query": "mud loss", "top_k": 3})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["results"] == []

    def test_documents_search_serialises_results(self, client, monkeypatch):
        import api.routers.documents as docs_router
        from document_retrieval.models import DocumentSearchResult

        result = DocumentSearchResult(
            chunk_id="c1", document_id="d1", file_name="report.pdf",
            page_number=14, chunk_index=3, section=None,
            text="mud losses observed at 3215m",
            similarity=0.87, rank=1,
        )
        monkeypatch.setattr(docs_router, "search_documents", lambda **k: [result])

        resp = client.post("/documents/search", json={"query": "mud loss"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        r = body["results"][0]
        assert r["file_name"] == "report.pdf"
        assert r["page_number"] == 14
        assert r["similarity"] == 0.87

    def test_document_metadata_not_found(self, client, fake_conn):
        fake_conn.cursor().set_rows([None])
        resp = client.get("/documents/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 404

    def test_document_metadata_reports_handwriting(self, client, fake_conn):
        cur = fake_conn.cursor()
        doc_id = "00000000-0000-0000-0000-000000000042"
        # First fetchone → document row.  Then fetchall → page rows.
        cur.set_rows([
            (doc_id, "report.pdf", "pdf", 3),
            (1, True, 88.0, "typed", 0.9, "not_needed", "typed"),
            (2, True, 55.0, "handwritten", 0.75, "detected_ocr_low_confidence", "handwritten"),
            (3, True, 90.0, "mixed", 0.6, "detected_ocr_success", "mixed"),
        ])
        resp = client.get(f"/documents/{doc_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["file_name"] == "report.pdf"
        assert body["handwriting_detected"] is True
        assert body["handwriting_page_count"] == 2
        assert len(body["pages"]) == 3


# ── Config-side sanity ──────────────────────────────────────

class TestConfig:
    def test_env_overrides_db_settings(self, monkeypatch):
        from api.config import get_api_settings, reset_api_settings_cache

        monkeypatch.setenv("API_DB_HOST", "example.internal")
        monkeypatch.setenv("API_DB_PORT", "9999")
        reset_api_settings_cache()
        try:
            settings = get_api_settings()
            assert settings.db_host == "example.internal"
            assert settings.db_port == 9999
            assert "example.internal" in settings.db_config()["host"]
        finally:
            reset_api_settings_cache()

    def test_no_api_keys_in_settings_repr(self, monkeypatch):
        from api.config import get_api_settings, reset_api_settings_cache

        monkeypatch.setenv("GROQ_API_KEY", "sk_secret_key_value_xxx")
        reset_api_settings_cache()
        try:
            settings = get_api_settings()
            # The secret value itself may live on the object; the check
            # here is that db_config() (used to build a connection
            # kwargs dict shown to logs) does NOT include the API key.
            assert "sk_secret" not in str(settings.db_config())
        finally:
            monkeypatch.delenv("GROQ_API_KEY", raising=False)
            reset_api_settings_cache()


# ── Live-DB integration tests ─────────────────────────────────

@pytest.mark.integration
class TestNewRoutersIntegration:
    @pytest.fixture
    def real_client(self):
        from api.app import app
        with TestClient(app) as c:
            yield c

    def test_risk_assess_real(self, real_client):
        resp = real_client.get(
            "/risk/assess",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["assessments"]) == 5
        assert all(a["methodology"] == "evidence_rule_based"
                   for a in body["assessments"])

    def test_events_well_real(self, real_client):
        resp = real_client.get(
            "/events/well",
            params={"dataset": "VOLVE", "well_id": "15/9-F-1"},
        )
        assert resp.status_code == 200
        # Even if no events are stored, the endpoint must respond cleanly.
        assert "events" in resp.json()

    def test_structured_query_real(self, real_client):
        resp = real_client.post(
            "/query/structured",
            json={
                "structured_query": {
                    "intent": "similar_wells",
                    "target_dataset": "VOLVE",
                    "target_well_id": "15/9-F-1",
                    "top_k": 3,
                }
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"]
        assert body["structured_query"]["intent"] == "similar_wells"
        assert body["confidence_score"]["is_probability"] is False
