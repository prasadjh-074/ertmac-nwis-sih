"""Tests for the evidence fusion, provenance, and rationale layer."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.fusion import fuse_evidence, _deduplicate, _detect_differences, _detect_missing
from evidence.models import (
    EvidenceGroup,
    FusedEvidence,
    FusedEvidenceItem,
    MissingInfo,
    ProvenanceRecord,
    SourceDifference,
)
from evidence.provenance import build_provenance, collect_source_systems, get_source_type
from evidence.rationale import generate_confidence_basis, generate_rationale
from graph.state import EvidenceItem
from resolver.models import ResolutionResult


# ============================================================
# Evidence creation
# ============================================================

class TestEvidenceCreation:
    def test_fuse_single_vector_evidence(self):
        ev = EvidenceItem(
            source_system="VOLVE", entity_type="well",
            well_id="15/9-F-4", similarity=0.92,
            metadata={"rank": 1, "windows_total": 100},
        )
        fused = fuse_evidence([ev], intent="similar_wells")
        assert fused.item_count == 1
        item = fused.items[0]
        assert item.source_system == "VOLVE"
        assert item.source_type == "vector_similarity"
        assert item.similarity == 0.92
        assert item.evidence_id == "ev-000"

    def test_fuse_sodir_evidence(self):
        ev = EvidenceItem(
            source_system="SODIR", entity_type="formation",
            well_id="15/9-19 SR", source_id="80",
            metadata={"formation_name": "UTSIRA FM", "top_depth_m": 846.0},
        )
        fused = fuse_evidence([ev], intent="formation_information")
        item = fused.items[0]
        assert item.source_system == "SODIR"
        assert item.source_type == "formation_top"
        assert item.entity_type == "formation"
        assert "UTSIRA FM" in item.explanation

    def test_fuse_well_info_evidence(self):
        ev = EvidenceItem(
            source_system="SODIR", entity_type="well_info",
            well_id="15/9-F-1", source_id="6419",
            metadata={"field_name": "VOLVE", "operator": "Statoil"},
        )
        fused = fuse_evidence([ev], intent="well_information")
        item = fused.items[0]
        assert item.source_type == "wellbore_record"
        assert "6419" in item.explanation

    def test_empty_evidence_returns_empty_fused(self):
        fused = fuse_evidence([])
        assert fused.item_count == 0
        assert fused.items == []

    def test_evidence_ids_sequential(self):
        evs = [
            EvidenceItem(source_system="VOLVE", entity_type="well", well_id=f"w{i}", similarity=0.9 - i * 0.1)
            for i in range(5)
        ]
        fused = fuse_evidence(evs)
        ids = [item.evidence_id for item in fused.items]
        assert ids == [f"ev-{i:03d}" for i in range(5)]


# ============================================================
# Provenance
# ============================================================

class TestProvenance:
    def test_vector_provenance(self):
        ev = EvidenceItem(source_system="FORCE_2020", entity_type="well", well_id="34/6-1", similarity=0.85)
        prov = build_provenance(ev)
        assert prov.source_system == "FORCE_2020"
        assert prov.retrieval_mechanism == "vector_similarity"
        assert prov.dataset == "FORCE_2020"

    def test_sodir_provenance(self):
        ev = EvidenceItem(source_system="SODIR", entity_type="formation", source_id="80")
        prov = build_provenance(ev)
        assert prov.retrieval_mechanism == "sodir_relational"
        assert prov.dataset is None

    def test_collect_source_systems_preserves_order(self):
        evs = [
            EvidenceItem(source_system="VOLVE", entity_type="well"),
            EvidenceItem(source_system="FORCE_2020", entity_type="well"),
            EvidenceItem(source_system="VOLVE", entity_type="well"),
        ]
        systems = collect_source_systems(evs)
        assert systems == ["VOLVE", "FORCE_2020"]

    def test_get_source_type_mapping(self):
        assert get_source_type("well") == "vector_similarity"
        assert get_source_type("formation") == "formation_top"
        assert get_source_type("well_info") == "wellbore_record"
        assert get_source_type("company") == "company_record"
        assert get_source_type("unknown_type") == "unknown_type"

    def test_every_fused_item_has_provenance(self):
        evs = [
            EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.9),
            EvidenceItem(source_system="SODIR", entity_type="formation"),
        ]
        fused = fuse_evidence(evs)
        for item in fused.items:
            assert isinstance(item.provenance, ProvenanceRecord)
            assert item.provenance.source_system


# ============================================================
# Deduplication
# ============================================================

class TestDeduplication:
    def test_removes_duplicates(self):
        ev = EvidenceItem(source_system="VOLVE", entity_type="well", well_id="15/9-F-4", similarity=0.92)
        fused = fuse_evidence([ev, ev])
        assert fused.item_count == 1

    def test_preserves_distinct_items(self):
        ev1 = EvidenceItem(source_system="VOLVE", entity_type="well", well_id="15/9-F-4", similarity=0.92)
        ev2 = EvidenceItem(source_system="FORCE_2020", entity_type="well", well_id="34/6-1", similarity=0.85)
        fused = fuse_evidence([ev1, ev2])
        assert fused.item_count == 2

    def test_different_similarity_not_deduped(self):
        ev1 = EvidenceItem(source_system="VOLVE", entity_type="well", well_id="15/9-F-4", similarity=0.92)
        ev2 = EvidenceItem(source_system="VOLVE", entity_type="well", well_id="15/9-F-4", similarity=0.85)
        fused = fuse_evidence([ev1, ev2])
        assert fused.item_count == 2


# ============================================================
# Evidence grouping
# ============================================================

class TestEvidenceGrouping:
    def test_groups_by_entity_type(self):
        evs = [
            EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.9),
            EvidenceItem(source_system="FORCE_2020", entity_type="well", similarity=0.85),
            EvidenceItem(source_system="SODIR", entity_type="formation"),
        ]
        fused = fuse_evidence(evs)
        assert len(fused.groups) == 2
        types = {g.entity_type for g in fused.groups}
        assert types == {"well", "formation"}

    def test_group_contains_correct_items(self):
        evs = [
            EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.9),
            EvidenceItem(source_system="SODIR", entity_type="formation", source_id="80"),
            EvidenceItem(source_system="SODIR", entity_type="formation", source_id="81"),
        ]
        fused = fuse_evidence(evs)
        formation_group = [g for g in fused.groups if g.entity_type == "formation"][0]
        assert len(formation_group.items) == 2

    def test_group_source_systems(self):
        evs = [
            EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.9),
            EvidenceItem(source_system="FORCE_2020", entity_type="well", similarity=0.85),
        ]
        fused = fuse_evidence(evs)
        well_group = fused.groups[0]
        assert set(well_group.source_systems) == {"VOLVE", "FORCE_2020"}


# ============================================================
# Conflict representation
# ============================================================

class TestConflictHandling:
    def test_detects_source_difference(self):
        ev1 = EvidenceItem(
            source_system="FORCE_2020", entity_type="well_info",
            well_id="15/9-F-1", metadata={"lithology": "65000"},
        )
        ev2 = EvidenceItem(
            source_system="VOLVE", entity_type="well_info",
            well_id="15/9-F-1", metadata={"lithology": "SST-CALC-ARG"},
        )
        fused = fuse_evidence([ev1, ev2])
        assert len(fused.differences) == 1
        diff = fused.differences[0]
        assert diff.difference_type == "source_difference"
        assert diff.field_name == "lithology"
        assert diff.source_a in ("FORCE_2020", "VOLVE")
        assert diff.source_b in ("FORCE_2020", "VOLVE")

    def test_no_conflict_when_values_agree(self):
        ev1 = EvidenceItem(
            source_system="FORCE_2020", entity_type="well_info",
            well_id="15/9-F-1", metadata={"operator": "Equinor"},
        )
        ev2 = EvidenceItem(
            source_system="VOLVE", entity_type="well_info",
            well_id="15/9-F-1", metadata={"operator": "Equinor"},
        )
        fused = fuse_evidence([ev1, ev2])
        assert len(fused.differences) == 0

    def test_no_conflict_for_single_source(self):
        ev1 = EvidenceItem(
            source_system="SODIR", entity_type="formation",
            well_id="15/9-19 SR", metadata={"formation_name": "UTSIRA FM"},
        )
        fused = fuse_evidence([ev1])
        assert fused.differences == []


# ============================================================
# Missing evidence
# ============================================================

class TestMissingEvidence:
    def test_missing_when_no_resolution(self):
        fused = fuse_evidence([], resolution_result=None)
        assert any(m.info_type == "no_resolution" for m in fused.missing)

    def test_missing_when_not_found(self):
        rr = ResolutionResult(
            intent="well_information", status="not_found",
            query={}, results={}, result_count=0, sources=[],
        )
        fused = fuse_evidence([], resolution_result=rr)
        assert any(m.info_type == "not_found" for m in fused.missing)

    def test_missing_when_partial(self):
        rr = ResolutionResult(
            intent="well_information", status="partial",
            query={}, results={"well_id": "15/9-F-1", "dataset": "FORCE_2020"},
            result_count=1, sources=["FORCE_2020"],
        )
        ev = EvidenceItem(source_system="FORCE_2020", entity_type="well_info", well_id="15/9-F-1")
        fused = fuse_evidence([ev], resolution_result=rr)
        assert any(m.info_type == "partial_data" for m in fused.missing)

    def test_missing_no_sodir_link(self):
        rr = ResolutionResult(
            intent="well_information", status="partial",
            query={}, results={"well_id": "34/6-1", "dataset": "FORCE_2020"},
            result_count=1, sources=["FORCE_2020"],
        )
        ev = EvidenceItem(source_system="FORCE_2020", entity_type="well_info", well_id="34/6-1")
        fused = fuse_evidence([ev], resolution_result=rr)
        assert any(m.info_type == "no_sodir_link" for m in fused.missing)

    def test_missing_no_formations(self):
        rr = ResolutionResult(
            intent="formation_information", status="success",
            query={}, results=[], result_count=0, sources=["VOLVE", "SODIR"],
        )
        fused = fuse_evidence([], resolution_result=rr, intent="formation_information")
        assert any(m.info_type == "no_formations" for m in fused.missing)

    def test_missing_distinguishes_not_found_from_not_linked(self):
        rr_nf = ResolutionResult(
            intent="well_information", status="not_found",
            query={}, results={}, result_count=0, sources=[],
        )
        fused_nf = fuse_evidence([], resolution_result=rr_nf)

        rr_partial = ResolutionResult(
            intent="well_information", status="partial",
            query={}, results={"well_id": "X", "dataset": "FORCE_2020"},
            result_count=1, sources=["FORCE_2020"],
        )
        ev = EvidenceItem(source_system="FORCE_2020", entity_type="well_info", well_id="X")
        fused_partial = fuse_evidence([ev], resolution_result=rr_partial)

        nf_reasons = {m.reason for m in fused_nf.missing}
        partial_reasons = {m.reason for m in fused_partial.missing}
        assert "not_found" in nf_reasons
        assert "not_linked" in partial_reasons


# ============================================================
# Rationale generation
# ============================================================

class TestRationale:
    def test_similar_wells_rationale(self):
        evs = [
            EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.92),
            EvidenceItem(source_system="FORCE_2020", entity_type="well", similarity=0.85),
        ]
        fused = fuse_evidence(evs, intent="similar_wells")
        rationale = generate_rationale("similar_wells", fused)
        assert any("cosine similarity" in r.lower() for r in rationale)
        assert any("2 evidence item" in r for r in rationale)

    def test_well_information_rationale(self):
        ev = EvidenceItem(source_system="SODIR", entity_type="well_info", source_id="6419")
        fused = fuse_evidence([ev], intent="well_information")
        rationale = generate_rationale("well_information", fused)
        assert any("SODIR" in r for r in rationale)

    def test_formation_rationale(self):
        ev = EvidenceItem(source_system="SODIR", entity_type="formation")
        fused = fuse_evidence([ev], intent="formation_information")
        rationale = generate_rationale("formation_information", fused)
        assert any("formation" in r.lower() for r in rationale)

    def test_rationale_mentions_provenance(self):
        evs = [
            EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.9),
            EvidenceItem(source_system="SODIR", entity_type="well_info"),
        ]
        fused = fuse_evidence(evs)
        rationale = generate_rationale("similar_wells", fused)
        assert any("source system" in r.lower() for r in rationale)

    def test_rationale_mentions_missing(self):
        rr = ResolutionResult(
            intent="formation_information", status="success",
            query={}, results=[], result_count=0, sources=["VOLVE", "SODIR"],
        )
        fused = fuse_evidence([], resolution_result=rr, intent="formation_information")
        rationale = generate_rationale("formation_information", fused)
        assert any("missing" in r.lower() for r in rationale)

    def test_empty_fused_rationale(self):
        fused = FusedEvidence()
        rationale = generate_rationale("similar_wells", fused)
        assert any("cosine similarity" in r.lower() for r in rationale)


# ============================================================
# Similarity evidence
# ============================================================

class TestSimilarityEvidence:
    def test_high_similarity_relevance(self):
        ev = EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.95)
        fused = fuse_evidence([ev])
        assert fused.items[0].relevance == "high"

    def test_moderate_similarity_relevance(self):
        ev = EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.75)
        fused = fuse_evidence([ev])
        assert fused.items[0].relevance == "moderate"

    def test_low_similarity_relevance(self):
        ev = EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.5)
        fused = fuse_evidence([ev])
        assert fused.items[0].relevance == "low"

    def test_similarity_in_explanation(self):
        ev = EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.92)
        fused = fuse_evidence([ev])
        assert "0.920" in fused.items[0].explanation


# ============================================================
# SODIR evidence
# ============================================================

class TestSODIREvidence:
    def test_sodir_relevance_is_direct(self):
        ev = EvidenceItem(source_system="SODIR", entity_type="well_info", source_id="6419")
        fused = fuse_evidence([ev])
        assert fused.items[0].relevance == "direct"

    def test_formation_relevance_is_direct(self):
        ev = EvidenceItem(source_system="SODIR", entity_type="formation", source_id="80")
        fused = fuse_evidence([ev])
        assert fused.items[0].relevance == "direct"


# ============================================================
# Confidence explanation
# ============================================================

class TestConfidenceExplanation:
    def test_basis_for_success(self):
        factors = {
            "status_component": 1.0,
            "presence_component": 1.0,
            "similarity_component": 0.9,
            "provenance_component": 1.0,
            "result_count": 5,
            "sources": ["VOLVE", "FORCE_2020"],
        }
        fused = FusedEvidence(item_count=5)
        basis = generate_confidence_basis(factors, fused)
        assert any("resolved successfully" in b for b in basis)
        assert any("5 retrieval" in b for b in basis)
        assert any("provenance" in b for b in basis)
        assert any("similarity" in b.lower() for b in basis)

    def test_basis_for_failure(self):
        factors = {
            "status_component": 0.0,
            "result_count": 0,
            "sources": [],
            "similarity_component": 0.0,
        }
        fused = FusedEvidence()
        basis = generate_confidence_basis(factors, fused)
        assert any("failed" in b or "no data" in b for b in basis)
        assert any("no retrieval" in b for b in basis)
        assert any("no provenance" in b for b in basis)

    def test_basis_is_not_probability(self):
        factors = {"status_component": 1.0, "result_count": 1, "sources": ["VOLVE"], "similarity_component": 0.5}
        fused = FusedEvidence(item_count=1)
        basis = generate_confidence_basis(factors, fused)
        assert all("probability" not in b.lower() for b in basis)


# ============================================================
# Document evidence (384-dim space, kept separate from vector_similarity)
# ============================================================

class TestDocumentEvidence:
    def test_fuse_document_evidence(self):
        ev = EvidenceItem(
            source_system="DOCUMENT", entity_type="document_chunk",
            source_id="c1", similarity=0.82,
            metadata={"file_name": "report.pdf", "page_number": 2, "text": "Heimdal 2450m"},
        )
        fused = fuse_evidence([ev], intent="document_search")
        item = fused.items[0]
        assert item.source_system == "DOCUMENT"
        assert item.source_type == "document"
        assert "report.pdf" in item.explanation
        assert "0.820" in item.explanation

    def test_document_provenance_mechanism(self):
        ev = EvidenceItem(source_system="DOCUMENT", entity_type="document_chunk", source_id="c1")
        prov = build_provenance(ev)
        assert prov.retrieval_mechanism == "document_vector_similarity"
        assert prov.dataset is None

    def test_document_source_type_mapping(self):
        assert get_source_type("document_chunk") == "document"

    def test_empty_document_search_reports_missing(self):
        fused = fuse_evidence([], intent="document_search")
        assert any(m.info_type == "no_documents_found" for m in fused.missing)

    def test_document_search_never_reports_no_resolution(self):
        """document_search never produces a ResolutionResult by design -
        it must not be flagged as if resolution failed."""
        fused = fuse_evidence([], resolution_result=None, intent="document_search")
        assert not any(m.info_type == "no_resolution" for m in fused.missing)

    def test_document_search_rationale(self):
        ev = EvidenceItem(
            source_system="DOCUMENT", entity_type="document_chunk",
            source_id="c1", similarity=0.75,
        )
        fused = fuse_evidence([ev], intent="document_search")
        rationale = generate_rationale("document_search", fused)
        assert any("384-dim" in r for r in rationale)
        assert any("Document evidence" in r for r in rationale)

    def test_combined_evidence_keeps_document_and_well_items_distinct(self):
        well_ev = EvidenceItem(source_system="VOLVE", entity_type="well", similarity=0.9)
        doc_ev = EvidenceItem(source_system="DOCUMENT", entity_type="document_chunk",
                               source_id="c1", similarity=0.6)
        fused = fuse_evidence([well_ev, doc_ev], intent="similar_wells")
        source_types = {i.source_type for i in fused.items}
        assert source_types == {"vector_similarity", "document"}
        assert set(fused.source_systems) == {"VOLVE", "DOCUMENT"}


# ============================================================
# Graph integration: fuse_evidence in pipeline
# ============================================================

class TestGraphIntegration:
    def test_fuse_evidence_node_in_pipeline(self):
        from graph import QueryGraphRunner
        runner = QueryGraphRunner(use_llm=False)
        resp = runner.run_structured_query({
            "intent": "similar_wells", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1", "top_k": 3,
        })
        assert resp.metadata.node_status.get("fuse_evidence") == "success"
        assert len(resp.rationale) > 0
        assert resp.confidence_score.basis is not None
        assert len(resp.confidence_score.basis) > 0
        assert resp.confidence_score.is_probability is False

    def test_rationale_present_for_all_intents(self):
        from graph import QueryGraphRunner
        runner = QueryGraphRunner(use_llm=False)

        queries = [
            {"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "top_k": 3},
            {"intent": "well_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1"},
            {"intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "15/9-19 SR"},
        ]
        for q in queries:
            resp = runner.run_structured_query(q)
            assert len(resp.rationale) > 0, f"No rationale for {q['intent']}"

    def test_confidence_basis_always_populated(self):
        from graph import QueryGraphRunner
        runner = QueryGraphRunner(use_llm=False)

        resp_ok = runner.run_structured_query({
            "intent": "similar_wells", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1", "top_k": 3,
        })
        assert len(resp_ok.confidence_score.basis) > 0

        resp_invalid = runner.run_structured_query({"intent": "similar_wells"})
        assert len(resp_invalid.confidence_score.basis) > 0

    @pytest.mark.integration
    def test_evidence_provenance_traceable(self):
        from graph import QueryGraphRunner
        runner = QueryGraphRunner(use_llm=False)
        resp = runner.run_structured_query({
            "intent": "well_information", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1",
        })
        for ev in resp.evidence:
            assert ev.source_system
            assert ev.entity_type
