"""
Tests for the structured query contract (query/schema.py, query/validator.py).
Pure schema validation - no database, no LLM, no network.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query import (
    DatasetEnum,
    QueryIntent,
    QueryValidationError,
    StructuredQuery,
    describe_errors,
    is_valid,
    validate_batch,
    validate_query,
)


# ============================================================
# The 5 worked examples from docs/query_contract.md - must all validate
# ============================================================

EXAMPLE_A = {"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "top_k": 10}
EXAMPLE_B = {
    "intent": "similar_windows", "target_dataset": "FORCE_2020",
    "target_well_id": "15/9-13 Sleipner East Appr", "target_window_id": 24,
    "top_k": 5, "min_curves_present": 6,
}
EXAMPLE_C = {
    "intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
    "requested_geological_context": ["formations", "stratigraphy"],
    "requested_output_fields": ["formations", "stratigraphic_units", "depth_range"],
}
EXAMPLE_D = {
    "intent": "compare_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-19 A",
    "comparison_dataset": "VOLVE", "comparison_well_id": "15/9-19 SR",
    "requested_geological_context": ["formations", "field"],
    "requested_output_fields": ["formations", "field_name"],
}
EXAMPLE_E = {
    "intent": "similar_wells", "target_dataset": "FORCE_2020",
    "target_well_id": "15/9-13 Sleipner East Appr", "dataset_filter": "VOLVE", "top_k": 5,
    "requested_geological_context": ["formations"],
    "requested_output_fields": ["formations", "similarity"],
}


@pytest.mark.parametrize("example", [EXAMPLE_A, EXAMPLE_B, EXAMPLE_C, EXAMPLE_D, EXAMPLE_E])
def test_worked_examples_are_valid(example):
    result = validate_query(example)
    assert isinstance(result, StructuredQuery)


def test_example_d_rejects_comparing_well_to_itself():
    bad = dict(EXAMPLE_D)
    bad["comparison_well_id"] = bad["target_well_id"]
    bad["comparison_dataset"] = bad["target_dataset"]
    with pytest.raises(QueryValidationError, match="not a valid comparison"):
        validate_query(bad)


# ============================================================
# Happy path: one valid construction per intent
# ============================================================

def test_similar_wells_minimal_valid():
    q = validate_query({"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1"})
    assert q.intent == QueryIntent.SIMILAR_WELLS


def test_similar_windows_minimal_valid():
    q = validate_query({
        "intent": "similar_windows", "target_dataset": "VOLVE",
        "target_well_id": "15/9-F-1", "target_window_id": 130,
    })
    assert q.target_window_id == 130


def test_well_information_minimal_valid():
    q = validate_query({"intent": "well_information", "target_dataset": "FORCE_2020", "target_well_id": "34/6-1"})
    assert q.intent == QueryIntent.WELL_INFORMATION


def test_formation_information_minimal_valid():
    q = validate_query({"intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1"})
    assert q.intent == QueryIntent.FORMATION_INFORMATION


def test_compare_wells_minimal_valid():
    q = validate_query({
        "intent": "compare_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-19 A",
        "comparison_dataset": "VOLVE", "comparison_well_id": "15/9-19 SR",
    })
    assert q.intent == QueryIntent.COMPARE_WELLS


def test_geological_context_minimal_valid():
    q = validate_query({"intent": "geological_context", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1"})
    assert q.intent == QueryIntent.GEOLOGICAL_CONTEXT


# ============================================================
# Missing required fields per intent
# ============================================================

@pytest.mark.parametrize("intent,payload", [
    ("similar_wells", {"target_dataset": "VOLVE"}),  # missing target_well_id
    ("similar_wells", {"target_well_id": "15/9-F-1"}),  # missing target_dataset
    ("similar_windows", {"target_dataset": "VOLVE", "target_well_id": "15/9-F-1"}),  # missing target_window_id
    ("compare_wells", {"target_dataset": "VOLVE", "target_well_id": "15/9-19 A"}),  # missing comparison_*
    ("well_information", {"target_dataset": "VOLVE"}),  # missing target_well_id
])
def test_missing_required_field_rejected(intent, payload):
    payload = dict(payload, intent=intent)
    with pytest.raises(QueryValidationError):
        validate_query(payload)


# ============================================================
# Forbidden / contradictory field combinations
# ============================================================

@pytest.mark.parametrize("payload", [
    {"intent": "well_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "top_k": 5},
    {"intent": "well_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "target_window_id": 1},
    {"intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "min_curves_present": 5},
    {"intent": "compare_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-19 A",
     "comparison_dataset": "VOLVE", "comparison_well_id": "15/9-19 SR", "top_k": 10},
    {"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "target_window_id": 5},
    {"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "min_curves_present": 5},
    {"intent": "geological_context", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "dataset_filter": "FORCE_2020"},
])
def test_forbidden_field_for_intent_rejected(payload):
    with pytest.raises(QueryValidationError, match="does not accept field"):
        validate_query(payload)


# ============================================================
# Numeric range validation
# ============================================================

@pytest.mark.parametrize("top_k", [0, -1, 51, 1000])
def test_top_k_out_of_range_rejected(top_k):
    with pytest.raises(QueryValidationError):
        validate_query({"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "top_k": top_k})


@pytest.mark.parametrize("top_k", [1, 10, 50])
def test_top_k_in_range_accepted(top_k):
    validate_query({"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1", "top_k": top_k})


@pytest.mark.parametrize("min_curves", [-1, 12, 100])
def test_min_curves_present_out_of_range_rejected(min_curves):
    with pytest.raises(QueryValidationError):
        validate_query({
            "intent": "similar_windows", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
            "target_window_id": 1, "min_curves_present": min_curves,
        })


@pytest.mark.parametrize("min_curves", [0, 4, 11])
def test_min_curves_present_in_range_accepted(min_curves):
    validate_query({
        "intent": "similar_windows", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
        "target_window_id": 1, "min_curves_present": min_curves,
    })


def test_negative_window_id_rejected():
    with pytest.raises(QueryValidationError):
        validate_query({
            "intent": "similar_windows", "target_dataset": "VOLVE",
            "target_well_id": "15/9-F-1", "target_window_id": -5,
        })


# ============================================================
# Enum validation
# ============================================================

def test_invalid_intent_rejected():
    with pytest.raises(QueryValidationError):
        validate_query({"intent": "delete_everything", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1"})


def test_invalid_dataset_rejected():
    with pytest.raises(QueryValidationError):
        validate_query({"intent": "similar_wells", "target_dataset": "NOT_A_REAL_DATASET", "target_well_id": "15/9-F-1"})


def test_invalid_geological_context_value_rejected():
    with pytest.raises(QueryValidationError):
        validate_query({
            "intent": "formation_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
            "requested_geological_context": ["not_a_real_context"],
        })


def test_invalid_output_field_rejected():
    with pytest.raises(QueryValidationError):
        validate_query({
            "intent": "well_information", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
            "requested_output_fields": ["raw_sql_column"],
        })


# ============================================================
# Malformed well_id (defense-in-depth against injection-shaped input)
# ============================================================

@pytest.mark.parametrize("bad_well_id", [
    "15/9-F-1'; DROP TABLE wells; --",
    "15/9-F-1\" OR 1=1",
    "'; SELECT * FROM core.wellbore; --",
    "well<script>alert(1)</script>",
    "",
])
def test_malformed_well_id_rejected(bad_well_id):
    with pytest.raises(QueryValidationError):
        validate_query({"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": bad_well_id})


def test_overlong_well_id_rejected():
    with pytest.raises(QueryValidationError):
        validate_query({"intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "A" * 101})


# ============================================================
# No SQL, no table names, no arbitrary code - structural guarantees
# ============================================================

def test_extra_unknown_field_rejected():
    with pytest.raises(QueryValidationError):
        validate_query({
            "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
            "raw_sql": "SELECT * FROM core.wellbore",
        })


def test_extra_code_field_rejected():
    with pytest.raises(QueryValidationError):
        validate_query({
            "intent": "similar_wells", "target_dataset": "VOLVE", "target_well_id": "15/9-F-1",
            "exec": "__import__('os').system('rm -rf /')",
        })


def test_schema_has_no_sql_or_table_name_fields():
    """Structural regression test: the model's field names themselves must
    never include anything that looks like a raw-SQL or table-name escape
    hatch, regardless of what future fields get added."""

    forbidden_substrings = ["sql", "table", "query_string", "raw_query", "exec", "eval", "code"]
    for field_name in StructuredQuery.model_fields:
        lowered = field_name.lower()
        for bad in forbidden_substrings:
            assert bad not in lowered, f"field '{field_name}' looks like it could carry {bad!r}"


def test_model_forbids_extra_by_config():
    assert StructuredQuery.model_config.get("extra") == "forbid"


# ============================================================
# validator.py helper functions
# ============================================================

def test_is_valid_true_for_good_input():
    assert is_valid(EXAMPLE_A) is True


def test_is_valid_false_for_bad_input():
    assert is_valid({"intent": "similar_wells"}) is False


def test_describe_errors_empty_for_valid():
    assert describe_errors(EXAMPLE_A) == []


def test_describe_errors_nonempty_for_invalid():
    errors = describe_errors({"intent": "similar_wells"})
    assert len(errors) > 0
    assert all(isinstance(e, str) for e in errors)


def test_validate_batch_splits_valid_and_invalid():
    valid, failures = validate_batch([EXAMPLE_A, {"intent": "similar_wells"}, EXAMPLE_B])
    assert len(valid) == 2
    assert len(failures) == 1
    assert failures[0][0] == 1  # index of the bad item


def test_validate_query_rejects_non_dict_input():
    with pytest.raises(QueryValidationError):
        validate_query("not a dict")
