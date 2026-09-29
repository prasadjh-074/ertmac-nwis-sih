"""Resolver-specific error hierarchy."""

from __future__ import annotations

from typing import List, Optional


class QueryResolutionError(Exception):
    """Base error for all resolver failures."""

    def __init__(self, message: str, intent: Optional[str] = None):
        self.intent = intent
        super().__init__(message)


class EntityNotFoundError(QueryResolutionError):
    """The target well, window, or formation does not exist in the data."""

    def __init__(self, entity_type: str, identifier: str, dataset: Optional[str] = None):
        self.entity_type = entity_type
        self.identifier = identifier
        self.dataset = dataset
        detail = f"{entity_type} {identifier!r}"
        if dataset:
            detail += f" in dataset {dataset!r}"
        super().__init__(f"Entity not found: {detail}")


class UnsupportedIntentError(QueryResolutionError):
    """The intent is not supported by the resolver."""

    def __init__(self, intent: str):
        super().__init__(f"Unsupported intent: {intent!r}", intent=intent)


class ResolverDataError(QueryResolutionError):
    """A database or data-access error during resolution."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        self.cause = cause
        super().__init__(message)
