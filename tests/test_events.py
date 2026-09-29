"""Tests for the drilling event intelligence system.

Unit tests run without a database.  Integration tests (marked @integration)
require a live PostgreSQL connection to geo_intelligence on localhost:5433.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from events.models import (
    DrillingEvent,
    EventProvenance,
    EventSeverity,
    EventType,
    CorrelatedEvent,
)
from events.extraction import (
    clean_html,
    extract_events_from_text,
    _extract_depths_from_context,
    _escalate_severity,
)

integration = pytest.mark.integration


# ── Models ──────────────────────────────────────────────────────────


class TestEventType:
    def test_all_10_types(self):
        assert len(EventType) == 10

    def test_string_values(self):
        assert EventType.MUD_LOSS.value == "mud_loss"
        assert EventType.STUCK_PIPE.value == "stuck_pipe"
        assert EventType.KICK.value == "kick"

    def test_from_string(self):
        assert EventType("mud_loss") == EventType.MUD_LOSS


class TestEventSeverity:
    def test_all_5_severities(self):
        assert len(EventSeverity) == 5

    def test_ordering_values(self):
        vals = [s.value for s in EventSeverity]
        assert "low" in vals
        assert "critical" in vals
        assert "unknown" in vals


class TestDrillingEvent:
    def test_defaults(self):
        ev = DrillingEvent()
        assert ev.event_type == EventType.OTHER
        assert ev.severity == EventSeverity.UNKNOWN
        assert ev.well_id == ""
        assert ev.indicators == []
        assert ev.metadata == {}
        assert ev.provenance.source_type == "unknown"

    def test_full_event(self):
        ev = DrillingEvent(
            event_id=1,
            well_id="15/9-F-1",
            dataset="VOLVE",
            event_type=EventType.STUCK_PIPE,
            depth_start_m=2500.0,
            depth_end_m=2550.0,
            formation="Heimdal",
            severity=EventSeverity.HIGH,
            description="stuck pipe at 2500 m",
            provenance=EventProvenance(
                source_type="sodir_history",
                source_table="subsurface.wellbore_history",
                source_record_id=42,
                extraction_method="regex_keyword",
                extraction_confidence=0.90,
            ),
            sodir_wellbore_id=1234,
        )
        assert ev.event_id == 1
        assert ev.formation == "Heimdal"
        assert ev.provenance.extraction_confidence == 0.90


class TestCorrelatedEvent:
    def test_creation(self):
        ev = DrillingEvent(well_id="A", dataset="FORCE", event_type=EventType.KICK)
        corr = CorrelatedEvent(
            event=ev,
            source_well_id="A",
            source_dataset="FORCE",
            distance_km=10.0,
            depth_overlap=True,
            formation_match=True,
        )
        assert corr.distance_km == 10.0
        assert corr.depth_overlap is True
        assert corr.formation_match is True

    def test_defaults(self):
        ev = DrillingEvent()
        corr = CorrelatedEvent(event=ev, source_well_id="X", source_dataset="Y")
        assert corr.distance_km is None
        assert corr.geological_similarity is None
        assert corr.depth_overlap is False
        assert corr.formation_match is False


# ── HTML Cleaning ───────────────────────────────────────────────────


class TestCleanHtml:
    def test_strip_tags(self):
        assert clean_html("<p>hello</p>") == "hello"

    def test_nested_tags(self):
        assert clean_html("<div><b>text</b></div>") == "text"

    def test_html_entities(self):
        assert clean_html("A &amp; B &lt;C&gt;") == "A & B <C>"

    def test_normalize_whitespace(self):
        assert clean_html("  a   b  \n c  ") == "a b c"

    def test_empty(self):
        assert clean_html("") == ""


# ── Depth Extraction ───────────────────────────────────────────────


class TestDepthExtraction:
    def test_single_depth(self):
        d1, d2 = _extract_depths_from_context("mud loss occurred at 870 m depth")
        assert d1 == 870.0
        assert d2 is None

    def test_depth_range(self):
        d1, d2 = _extract_depths_from_context("losses between 1200-1500 m")
        assert d1 == 1200.0
        assert d2 == 1500.0

    def test_multiple_depths(self):
        d1, d2 = _extract_depths_from_context("from 2000 m to 2500 m section")
        assert d1 == 2000.0
        assert d2 == 2500.0

    def test_no_depth(self):
        d1, d2 = _extract_depths_from_context("no depths mentioned here")
        assert d1 is None
        assert d2 is None

    def test_mMD(self):
        d1, d2 = _extract_depths_from_context("at 3500 mMD")
        assert d1 == 3500.0


# ── Severity Escalation ────────────────────────────────────────────


class TestSeverityEscalation:
    def test_severe_escalates(self):
        result = _escalate_severity(EventSeverity.MEDIUM, "severe losses encountered")
        assert result == EventSeverity.HIGH

    def test_total_loss_escalates_to_critical(self):
        result = _escalate_severity(EventSeverity.MEDIUM, "total loss of circulation")
        assert result == EventSeverity.CRITICAL

    def test_no_escalation(self):
        result = _escalate_severity(EventSeverity.LOW, "minor issue noted")
        assert result == EventSeverity.LOW

    def test_already_critical_stays(self):
        result = _escalate_severity(EventSeverity.CRITICAL, "severe major issue")
        assert result == EventSeverity.CRITICAL


# ── Event Extraction ───────────────────────────────────────────────


class TestExtractEventsFromText:
    def test_stuck_pipe(self):
        text = "Drilled to 2500 m. Stuck pipe encountered at 2450 m. Freed after 12 hours."
        events = extract_events_from_text(text, "W1", "FORCE")
        assert len(events) >= 1
        stuck = [e for e in events if e.event_type == EventType.STUCK_PIPE]
        assert len(stuck) == 1
        assert stuck[0].provenance.extraction_confidence == 0.90
        assert stuck[0].well_id == "W1"
        assert stuck[0].dataset == "FORCE"

    def test_mud_loss(self):
        text = "Mud losses occurred at 870 m in the 12 1/4 inch section."
        events = extract_events_from_text(text, "W2", "VOLVE")
        mud = [e for e in events if e.event_type == EventType.MUD_LOSS]
        assert len(mud) == 1
        assert mud[0].depth_start_m == 870.0

    def test_lost_circulation(self):
        text = "Lost circulation occurred at 2439 m."
        events = extract_events_from_text(text, "W3", "FORCE")
        mud = [e for e in events if e.event_type == EventType.MUD_LOSS]
        assert len(mud) == 1
        assert mud[0].subtype.lower() == "lost circulation"

    def test_kick_vs_kickoff_disambiguation(self):
        text = "Kick-off was made at 1039 m for sidetrack. No kick detected."
        events = extract_events_from_text(text, "W4", "FORCE")
        kicks = [e for e in events if e.event_type == EventType.KICK]
        # "Kick-off" should be excluded, but bare "kick" in "No kick detected" might match
        # The exclusion pattern checks +-30 chars around the "kick" match
        # "No kick detected" is far enough from "Kick-off" to potentially match
        for k in kicks:
            assert "kick-off" not in k.subtype.lower()
            assert "kicked off" not in k.subtype.lower()

    def test_fishing_operation(self):
        text = "Fishing operations were conducted to recover the drill string."
        events = extract_events_from_text(text, "W5", "FORCE")
        fishing = [e for e in events if e.event_type == EventType.FISHING]
        assert len(fishing) >= 1

    def test_html_input(self):
        text = "<p>Stuck pipe at <b>2500 m</b> in the <i>Heimdal Formation</i>.</p>"
        events = extract_events_from_text(text, "W6", "VOLVE")
        assert len(events) >= 1
        assert events[0].event_type == EventType.STUCK_PIPE

    def test_empty_text(self):
        assert extract_events_from_text("", "W7", "FORCE") == []

    def test_short_text(self):
        assert extract_events_from_text("OK", "W8", "FORCE") == []

    def test_provenance_fields(self):
        text = "Stuck pipe at 3000 m."
        events = extract_events_from_text(
            text, "W9", "FORCE",
            sodir_wellbore_id=123,
            source_record_id=456,
        )
        assert events[0].provenance.source_type == "sodir_history"
        assert events[0].provenance.source_table == "subsurface.wellbore_history"
        assert events[0].provenance.source_record_id == 456
        assert events[0].provenance.extraction_method == "regex_keyword"
        assert events[0].sodir_wellbore_id == 123

    def test_multiple_event_types(self):
        text = ("Stuck pipe at 2000 m. Lost circulation at 2100 m. "
                "Fishing operations to recover BHA.")
        events = extract_events_from_text(text, "W10", "FORCE")
        types = {e.event_type for e in events}
        assert EventType.STUCK_PIPE in types
        assert EventType.MUD_LOSS in types
        assert EventType.FISHING in types

    def test_deduplication_same_span(self):
        text = "Mud losses and more mud losses at same location."
        events = extract_events_from_text(text, "W11", "FORCE")
        mud = [e for e in events if e.event_type == EventType.MUD_LOSS]
        # Both "mud losses" are at different positions, so both should match
        assert len(mud) == 2

    def test_severity_escalation_in_context(self):
        text = "Severe mud losses encountered at 1500 m."
        events = extract_events_from_text(text, "W12", "FORCE")
        mud = [e for e in events if e.event_type == EventType.MUD_LOSS]
        assert len(mud) >= 1
        # The "severe losses" pattern itself has HIGH severity,
        # and "severe" in context should keep it HIGH
        high_or_above = [e for e in mud if e.severity in (EventSeverity.HIGH, EventSeverity.CRITICAL)]
        assert len(high_or_above) >= 1

    def test_npt_detection(self):
        text = "Total NPT for this section was 48 hours."
        events = extract_events_from_text(text, "W13", "FORCE")
        npt = [e for e in events if e.event_type == EventType.NPT]
        assert len(npt) == 1

    def test_overpressure_detection(self):
        text = "Overpressure was encountered below 3000 m."
        events = extract_events_from_text(text, "W14", "FORCE")
        op = [e for e in events if e.event_type == EventType.OVERPRESSURE]
        assert len(op) == 1

    def test_cementing_issue(self):
        text = "Cement squeeze performed due to cementing failure."
        events = extract_events_from_text(text, "W15", "FORCE")
        cement = [e for e in events if e.event_type == EventType.CEMENTING_ISSUE]
        assert len(cement) >= 1

    def test_casing_issue(self):
        text = "Casing leak was detected at 1800 m requiring remedial work."
        events = extract_events_from_text(text, "W16", "FORCE")
        casing = [e for e in events if e.event_type == EventType.CASING_ISSUE]
        assert len(casing) == 1

    def test_hole_instability(self):
        text = "Hole instability problems were encountered in the shale section."
        events = extract_events_from_text(text, "W17", "FORCE")
        other = [e for e in events if e.event_type == EventType.OTHER]
        assert len(other) >= 1


# ── Storage (mocked) ───────────────────────────────────────────────


class TestStorageMocked:
    def _make_event(self, well_id="W1", dataset="FORCE", event_type=EventType.STUCK_PIPE):
        return DrillingEvent(
            well_id=well_id,
            dataset=dataset,
            event_type=event_type,
            depth_start_m=2500.0,
            severity=EventSeverity.HIGH,
            description="test event",
            provenance=EventProvenance(
                source_type="sodir_history",
                extraction_method="regex_keyword",
                extraction_confidence=0.90,
            ),
        )

    @patch("events.storage.psycopg2.connect")
    def test_store_event(self, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (42,)
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        from events.storage import store_event
        ev = self._make_event()
        event_id = store_event(ev)
        assert event_id == 42
        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("events.storage.psycopg2.connect")
    def test_store_events_batch(self, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [(1,), (2,), (3,)]
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        from events.storage import store_events
        events = [self._make_event(well_id=f"W{i}") for i in range(3)]
        ids = store_events(events)
        assert ids == [1, 2, 3]
        assert mock_cur.execute.call_count == 3
        mock_conn.commit.assert_called_once()

    @patch("events.storage.psycopg2.connect")
    def test_store_events_empty(self, mock_connect):
        from events.storage import store_events
        assert store_events([]) == []
        mock_connect.assert_not_called()

    @patch("events.storage.psycopg2.connect")
    def test_count_events(self, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (100,)
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        from events.storage import count_events
        assert count_events() == 100


# ── Integration Tests ──────────────────────────────────────────────


@integration
class TestExtractionIntegration:
    """Test event extraction against real SODIR data."""

    def test_extract_for_known_well(self):
        from events.extraction import extract_events_for_well
        events = extract_events_for_well("15/9-F-1", "VOLVE")
        # Volve well 15/9-F-1 has SODIR history records
        assert isinstance(events, list)
        # Should extract at least some events from drilling narratives
        for ev in events:
            assert ev.well_id == "15/9-F-1"
            assert ev.dataset == "VOLVE"
            assert ev.provenance.source_type == "sodir_history"

    def test_extract_for_nonexistent_well(self):
        from events.extraction import extract_events_for_well
        events = extract_events_for_well("NONEXISTENT", "FORCE")
        assert events == []


@integration
class TestStorageIntegration:
    """Test event storage against real database."""

    def _make_test_event(self):
        return DrillingEvent(
            well_id="TEST/99-X-1",
            dataset="TEST",
            event_type=EventType.STUCK_PIPE,
            depth_start_m=2500.0,
            formation="TestFormation",
            severity=EventSeverity.HIGH,
            description="test stuck pipe",
            provenance=EventProvenance(
                source_type="test",
                extraction_method="test",
                extraction_confidence=0.99,
            ),
        )

    def test_store_and_load(self):
        import psycopg2
        from events.storage import store_event, load_events_for_well, delete_events_for_well

        conn = psycopg2.connect(host="localhost", port=5433, dbname="geo_intelligence", user="prasadhemadri99")
        try:
            ev = self._make_test_event()
            event_id = store_event(ev, conn=conn)
            conn.commit()
            assert event_id > 0

            loaded = load_events_for_well("TEST/99-X-1", "TEST", conn=conn)
            assert len(loaded) >= 1
            found = [e for e in loaded if e.event_id == event_id]
            assert len(found) == 1
            assert found[0].event_type == EventType.STUCK_PIPE
            assert found[0].depth_start_m == 2500.0
            assert found[0].formation == "TestFormation"
            assert found[0].provenance.extraction_confidence == 0.99

            delete_events_for_well("TEST/99-X-1", "TEST", conn=conn)
            conn.commit()
            remaining = load_events_for_well("TEST/99-X-1", "TEST", conn=conn)
            assert len(remaining) == 0
        finally:
            conn.close()

    def test_find_events_near_depth(self):
        import psycopg2
        from events.storage import store_events, find_events_near_depth, delete_events_for_well

        conn = psycopg2.connect(host="localhost", port=5433, dbname="geo_intelligence", user="prasadhemadri99")
        try:
            events = [
                DrillingEvent(
                    well_id="TEST/99-X-1", dataset="TEST",
                    event_type=EventType.MUD_LOSS,
                    depth_start_m=float(d), severity=EventSeverity.MEDIUM,
                    provenance=EventProvenance(source_type="test", extraction_method="test"),
                )
                for d in [1000, 1500, 2000, 2500, 3000]
            ]
            store_events(events, conn=conn)
            conn.commit()

            near = find_events_near_depth("TEST/99-X-1", "TEST", 2000.0, tolerance_m=100.0, conn=conn)
            assert len(near) == 1
            assert near[0].depth_start_m == 2000.0

            near_wide = find_events_near_depth("TEST/99-X-1", "TEST", 2000.0, tolerance_m=600.0, conn=conn)
            assert len(near_wide) == 3  # 1500, 2000, 2500

            delete_events_for_well("TEST/99-X-1", "TEST", conn=conn)
            conn.commit()
        finally:
            conn.close()

    def test_find_events_by_formation(self):
        import psycopg2
        from events.storage import store_event, find_events_by_formation, delete_events_for_well

        conn = psycopg2.connect(host="localhost", port=5433, dbname="geo_intelligence", user="prasadhemadri99")
        try:
            ev = DrillingEvent(
                well_id="TEST/99-X-1", dataset="TEST",
                event_type=EventType.KICK, formation="Heimdal",
                severity=EventSeverity.CRITICAL,
                provenance=EventProvenance(source_type="test", extraction_method="test"),
            )
            store_event(ev, conn=conn)
            conn.commit()

            results = find_events_by_formation("Heimdal", conn=conn)
            test_results = [r for r in results if r.well_id == "TEST/99-X-1"]
            assert len(test_results) >= 1
            assert test_results[0].formation == "Heimdal"

            # Case-insensitive
            results_lower = find_events_by_formation("heimdal", conn=conn)
            test_lower = [r for r in results_lower if r.well_id == "TEST/99-X-1"]
            assert len(test_lower) >= 1

            delete_events_for_well("TEST/99-X-1", "TEST", conn=conn)
            conn.commit()
        finally:
            conn.close()


@integration
class TestCorrelationIntegration:
    """Test correlation service against real data.
    Requires events to have been extracted and stored first."""

    def test_correlate_returns_list(self):
        from events.correlation import correlate_historical_events
        results = correlate_historical_events(
            "15/9-F-1", "VOLVE",
            current_depth_m=2500.0,
            radius_km=50.0,
            limit=5,
        )
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, CorrelatedEvent)
            assert "score" in r.relevance_factors

    def test_correlate_nonexistent_well(self):
        from events.correlation import correlate_historical_events
        results = correlate_historical_events(
            "NONEXISTENT", "FORCE",
            limit=5,
        )
        assert isinstance(results, list)
