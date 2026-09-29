"""
Thin validation entry point for the structured query contract.

This is where an eventual LLM's raw JSON output would be handed off for
validation - nothing here executes anything, connects to a database, or
runs a model. It only ever returns a validated StructuredQuery or raises/
reports errors.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pydantic import ValidationError

from .schema import StructuredQuery


class QueryValidationError(Exception):
    """Raised by validate_query on malformed or contradictory input.
    Wraps pydantic's ValidationError with a flat list of human-readable
    messages, so a caller never needs to know pydantic's error shape."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _flatten_pydantic_errors(exc: ValidationError) -> List[str]:
    messages = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err["loc"]) or "<root>"
        messages.append(f"{location}: {err['msg']}")
    return messages


def validate_query(data: Dict[str, Any]) -> StructuredQuery:
    """Validate a raw dict (e.g. parsed from an LLM's JSON output) against
    the StructuredQuery contract. Returns the validated model on success;
    raises QueryValidationError with readable messages on failure."""

    if not isinstance(data, dict):
        raise QueryValidationError([f"input must be a dict, got {type(data).__name__}"])

    try:
        return StructuredQuery.model_validate(data)
    except ValidationError as exc:
        raise QueryValidationError(_flatten_pydantic_errors(exc)) from exc


def is_valid(data: Dict[str, Any]) -> bool:
    """True/False check with no exception - convenient for quick filtering."""
    try:
        validate_query(data)
        return True
    except QueryValidationError:
        return False


def describe_errors(data: Dict[str, Any]) -> List[str]:
    """Return the list of validation error messages for invalid input, or
    an empty list if the input is valid."""

    try:
        validate_query(data)
        return []
    except QueryValidationError as exc:
        return exc.errors


def validate_batch(items: List[Dict[str, Any]]) -> Tuple[List[StructuredQuery], List[Tuple[int, List[str]]]]:
    """Validate a list of candidate queries. Returns (valid_queries,
    failures) where failures is a list of (index, error_messages)."""

    valid: List[StructuredQuery] = []
    failures: List[Tuple[int, List[str]]] = []

    for i, item in enumerate(items):
        try:
            valid.append(validate_query(item))
        except QueryValidationError as exc:
            failures.append((i, exc.errors))

    return valid, failures
