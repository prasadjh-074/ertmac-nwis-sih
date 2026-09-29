from dotenv import load_dotenv
load_dotenv()

"""
Tests for the Groq → StructuredQuery interpreter (llm/).

Mocked tests run without a Groq API key. Live tests (marked with
@pytest.mark.live) run only when GROQ_API_KEY is set and pytest is
invoked with -m live.
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm import GroqInterpreter, InterpretationError, InterpretationResult
from query import QueryIntent, StructuredQuery


# ============================================================
# Helpers for mocking Groq API responses
# ============================================================

def _make_groq_response(content: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


def _make_interpreter_with_mock(response_content: str):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_groq_response(response_content)
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-real"}):
        interp = GroqInterpreter(_client=mock_client)
    return interp, mock_client


# ============================================================
# Test A: "Find wells similar to 15/9-F-1"
# ============================================================

def test_a_find_similar_wells():
    response = json.dumps({
        "intent": "similar_wells",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "top_k": 10,
    })
    interp, _ = _make_interpreter_with_mock(response)
    result = interp.interpret("Find wells similar to 15/9-F-1")
    assert isinstance(result, InterpretationResult)
    assert result.query.intent == QueryIntent.SIMILAR_WELLS
    assert result.query.target_well_id == "15/9-F-1"
    assert result.query.top_k == 10


# ============================================================
# Test B: "Find intervals similar to FORCE window 24 of well 15/9-13"
# ============================================================

def test_b_find_similar_windows():
    response = json.dumps({
        "intent": "similar_windows",
        "target_dataset": "FORCE_2020",
        "target_well_id": "15/9-13 Sleipner East Appr",
        "target_window_id": 24,
        "top_k": 5,
        "min_curves_present": 6,
    })
    interp, _ = _make_interpreter_with_mock(response)
    result = interp.interpret("Find 5 intervals similar to window 24 of FORCE well 15/9-13 Sleipner East Appr with at least 6 curves")
    assert result.query.intent == QueryIntent.SIMILAR_WINDOWS
    assert result.query.target_window_id == 24
    assert result.query.min_curves_present == 6


# ============================================================
# Test C: "What formations does well 15/9-F-1 pass through?"
# ============================================================

def test_c_formation_information():
    response = json.dumps({
        "intent": "formation_information",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "requested_geological_context": ["formations", "stratigraphy"],
        "requested_output_fields": ["formations", "stratigraphic_units", "depth_range"],
    })
    interp, _ = _make_interpreter_with_mock(response)
    result = interp.interpret("What formations does well 15/9-F-1 pass through?")
    assert result.query.intent == QueryIntent.FORMATION_INFORMATION
    assert len(result.query.requested_geological_context) == 2


# ============================================================
# Test D: "Compare wells 15/9-19 A and 15/9-19 SR"
# ============================================================

def test_d_compare_wells():
    response = json.dumps({
        "intent": "compare_wells",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-19 A",
        "comparison_dataset": "VOLVE",
        "comparison_well_id": "15/9-19 SR",
        "requested_geological_context": ["formations", "field"],
        "requested_output_fields": ["formations", "field_name"],
    })
    interp, _ = _make_interpreter_with_mock(response)
    result = interp.interpret("Compare wells 15/9-19 A and 15/9-19 SR")
    assert result.query.intent == QueryIntent.COMPARE_WELLS
    assert result.query.comparison_well_id == "15/9-19 SR"


# ============================================================
# Test E: "Tell me about well 34/6-1"
# ============================================================

def test_e_well_information():
    response = json.dumps({
        "intent": "well_information",
        "target_dataset": "FORCE_2020",
        "target_well_id": "34/6-1",
    })
    interp, _ = _make_interpreter_with_mock(response)
    result = interp.interpret("Tell me about well 34/6-1")
    assert result.query.intent == QueryIntent.WELL_INFORMATION
    assert result.query.target_well_id == "34/6-1"


# ============================================================
# Test F: "What is the geological context of well 15/9-F-4?"
# ============================================================

def test_f_geological_context():
    response = json.dumps({
        "intent": "geological_context",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-4",
        "requested_geological_context": ["field", "company"],
        "requested_output_fields": ["field_name", "operator"],
    })
    interp, _ = _make_interpreter_with_mock(response)
    result = interp.interpret("What is the geological context of well 15/9-F-4 including its field and operator?")
    assert result.query.intent == QueryIntent.GEOLOGICAL_CONTEXT
    assert result.query.target_well_id == "15/9-F-4"


# ============================================================
# Negative / safety tests
# ============================================================

def test_rejects_empty_question():
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-real"}):
        interp = GroqInterpreter(_client=MagicMock())
    with pytest.raises(InterpretationError, match="non-empty"):
        interp.interpret("")


def test_rejects_whitespace_only_question():
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-real"}):
        interp = GroqInterpreter(_client=MagicMock())
    with pytest.raises(InterpretationError, match="non-empty"):
        interp.interpret("   ")


def test_invalid_json_from_groq_raises_after_retries():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_groq_response("not json at all")
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-real"}):
        interp = GroqInterpreter(_client=mock_client)
    with pytest.raises(InterpretationError, match="invalid JSON"):
        interp.interpret("Find similar wells to 15/9-F-1")
    assert mock_client.chat.completions.create.call_count == 3  # 1 + 2 retries


def test_schema_violation_from_groq_raises_after_retries():
    bad_json = json.dumps({"intent": "similar_wells"})  # missing required fields
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_groq_response(bad_json)
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-real"}):
        interp = GroqInterpreter(_client=mock_client)
    with pytest.raises(InterpretationError, match="schema validation"):
        interp.interpret("Find similar wells")
    assert mock_client.chat.completions.create.call_count == 3


def test_sql_injection_in_question_produces_valid_query():
    """Even if the user's question contains SQL, the output must be a
    valid StructuredQuery (not SQL). The system prompt forbids SQL output."""
    response = json.dumps({
        "intent": "well_information",
        "target_dataset": "FORCE_2020",
        "target_well_id": "UNKNOWN",
    })
    interp, _ = _make_interpreter_with_mock(response)
    result = interp.interpret("SELECT * FROM core.wellbore; DROP TABLE wells;")
    assert isinstance(result.query, StructuredQuery)
    assert "SELECT" not in json.dumps(result.raw_json)


def test_extra_fields_from_groq_are_rejected_and_retried():
    """If Groq returns extra fields (extra='forbid'), validation fails and
    the interpreter retries with the error message."""
    bad = json.dumps({
        "intent": "similar_wells",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "top_k": 10,
        "raw_sql": "SELECT * FROM wells",
    })
    good = json.dumps({
        "intent": "similar_wells",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "top_k": 10,
    })
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _make_groq_response(bad),
        _make_groq_response(good),
    ]
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-real"}):
        interp = GroqInterpreter(_client=mock_client)
    result = interp.interpret("Find similar wells to 15/9-F-1")
    assert result.query.intent == QueryIntent.SIMILAR_WELLS
    assert result.retries == 1


def test_no_api_key_raises():
    with patch.dict(os.environ, {}, clear=True), \
         patch("llm.groq_interpreter.load_dotenv"):
        os.environ.pop("GROQ_API_KEY", None)
        with pytest.raises(InterpretationError, match="GROQ_API_KEY"):
            GroqInterpreter()


def test_groq_api_exception_raises():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("connection timeout")
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-real"}):
        interp = GroqInterpreter(_client=mock_client)
    with pytest.raises(InterpretationError, match="API call failed"):
        interp.interpret("Find similar wells")


# ============================================================
# Observability metadata
# ============================================================

def test_result_contains_metadata():
    response = json.dumps({
        "intent": "well_information",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
    })
    interp, _ = _make_interpreter_with_mock(response)
    result = interp.interpret("Tell me about 15/9-F-1")
    assert isinstance(result.model, str) and len(result.model) > 0
    assert result.latency_ms >= 0
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 50
    assert result.retries == 0
    assert isinstance(result.raw_json, dict)


# ============================================================
# Retry logic: first attempt fails validation, second succeeds
# ============================================================

def test_retry_on_validation_failure_succeeds():
    bad = json.dumps({"intent": "similar_wells", "target_dataset": "VOLVE"})
    good = json.dumps({
        "intent": "similar_wells",
        "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1",
        "top_k": 10,
    })
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _make_groq_response(bad),
        _make_groq_response(good),
    ]
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-real"}):
        interp = GroqInterpreter(_client=mock_client)
    result = interp.interpret("Find similar wells to 15/9-F-1")
    assert result.query.intent == QueryIntent.SIMILAR_WELLS
    assert result.retries == 1


# ============================================================
# Live tests (require GROQ_API_KEY, run with: pytest -m live)
# ============================================================

LIVE_REASON = "GROQ_API_KEY not set — skipping live test"
has_api_key = bool(os.getenv("GROQ_API_KEY"))


@pytest.mark.live
@pytest.mark.skipif(not has_api_key, reason=LIVE_REASON)
def test_live_a_similar_wells():
    interp = GroqInterpreter()
    result = interp.interpret("Find wells similar to 15/9-F-1")
    assert result.query.intent == QueryIntent.SIMILAR_WELLS
    assert "15/9-F-1" in result.query.target_well_id
    print(f"  model={result.model} latency={result.latency_ms:.0f}ms tokens={result.prompt_tokens}+{result.completion_tokens}")


@pytest.mark.live
@pytest.mark.skipif(not has_api_key, reason=LIVE_REASON)
def test_live_b_formation_info():
    interp = GroqInterpreter()
    result = interp.interpret("What formations does well 15/9-F-1 pass through?")
    assert result.query.intent == QueryIntent.FORMATION_INFORMATION
    print(f"  model={result.model} latency={result.latency_ms:.0f}ms")


@pytest.mark.live
@pytest.mark.skipif(not has_api_key, reason=LIVE_REASON)
def test_live_c_compare_wells():
    interp = GroqInterpreter()
    result = interp.interpret("Compare wells 15/9-F-1 and 15/9-F-4")
    assert result.query.intent == QueryIntent.COMPARE_WELLS
    print(f"  model={result.model} latency={result.latency_ms:.0f}ms")


@pytest.mark.live
@pytest.mark.skipif(not has_api_key, reason=LIVE_REASON)
def test_live_d_well_information():
    interp = GroqInterpreter()
    result = interp.interpret("Tell me about well 34/6-1")
    assert result.query.intent == QueryIntent.WELL_INFORMATION
    print(f"  model={result.model} latency={result.latency_ms:.0f}ms")


@pytest.mark.live
@pytest.mark.skipif(not has_api_key, reason=LIVE_REASON)
def test_live_e_geological_context():
    interp = GroqInterpreter()
    result = interp.interpret("What is the geological context of well 15/9-F-4 including field and operator info?")
    assert result.query.intent == QueryIntent.GEOLOGICAL_CONTEXT
    print(f"  model={result.model} latency={result.latency_ms:.0f}ms")


@pytest.mark.live
@pytest.mark.skipif(not has_api_key, reason=LIVE_REASON)
def test_live_f_sql_injection_safe():
    interp = GroqInterpreter()
    result = interp.interpret("'; DROP TABLE wells; -- find similar wells")
    assert isinstance(result.query, StructuredQuery)
    raw = json.dumps(result.raw_json)
    assert "DROP" not in raw
    assert "SELECT" not in raw
    print(f"  model={result.model} intent={result.query.intent.value}")
