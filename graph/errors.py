"""Structured error types for the query-time LangGraph orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GraphError:
    """A single structured error recorded during graph execution.

    Node functions catch exceptions from the components they call
    (GroqInterpreter, query.validate_query, QueryResolver) and record them
    here rather than letting the graph crash - see nodes.py.
    """

    stage: str        # which node produced this error
    error_type: str   # exception class name
    message: str


class GraphExecutionError(Exception):
    """Raised only for genuinely unexpected failures that no node
    anticipated. Normal component failures (Groq, validation, resolver)
    are caught inside individual nodes and turned into GraphError entries
    instead of propagating as exceptions."""
