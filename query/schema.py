"""
Structured query contract for the future LLM layer.

This is a schema ONLY - it has no knowledge of SQL, table names, or how a
query actually gets executed. An LLM (not yet integrated) will eventually
be asked to produce JSON matching StructuredQuery; a separate, later
resolver layer (not built here) will turn a validated StructuredQuery into
actual retrieval/graph calls. This file draws its vocabulary only from
concepts already established elsewhere in this project (dataset names,
the 11 shared curves, the SODIR graph entities) - nothing here is invented
ahead of what those layers already support.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Real well-name characters observed throughout this project, e.g.
# "15/9-F-1", "15/9-13 Sleipner East Appr", "34/6-1 S". Deliberately
# excludes quote/semicolon/SQL-comment characters - a well_id can never
# contain the characters that would make it look like injected SQL.
WELL_ID_PATTERN = r"^[A-Za-z0-9/\-_. ]+$"
WELL_ID_MAX_LENGTH = 100

# Matches the 11 shared curves used in the frozen core embedding
# (docs/embedding_design.md) - min_curves_present can never exceed this.
MAX_SHARED_CURVES = 11

TOP_K_MIN = 1
TOP_K_MAX = 50

# search_text is embedded (never used to build SQL text) via the same
# sentence-transformer model used at ingestion time - free-form natural
# language, but length-capped to prevent abuse.
SEARCH_TEXT_MAX_LENGTH = 500

# File names are stored verbatim from ingestion (see ingestion/schemas.py);
# this pattern excludes quote/semicolon/SQL-comment characters, same
# rationale as WELL_ID_PATTERN above.
DOCUMENT_FILE_NAME_PATTERN = r"^[A-Za-z0-9/\-_. ]+$"
DOCUMENT_FILE_NAME_MAX_LENGTH = 255


class DatasetEnum(str, Enum):
    """The only two datasets with embeddings/graph data loaded so far."""

    FORCE_2020 = "FORCE_2020"
    VOLVE = "VOLVE"


class QueryIntent(str, Enum):
    SIMILAR_WELLS = "similar_wells"
    SIMILAR_WINDOWS = "similar_windows"
    WELL_INFORMATION = "well_information"
    FORMATION_INFORMATION = "formation_information"
    COMPARE_WELLS = "compare_wells"
    GEOLOGICAL_CONTEXT = "geological_context"
    DOCUMENT_SEARCH = "document_search"


class DocumentSourceType(str, Enum):
    """Mirrors ingestion/schemas.py's SourceType literal - the only source
    types the ingestion pipeline actually produces."""

    PDF = "pdf"
    TEXT = "text"
    IMAGE = "image"


class GeologicalContextField(str, Enum):
    """Mirrors the SODIR graph entities from
    docs/sodir_knowledge_graph_design.md - a semantic label, not a table
    name (e.g. FORMATIONS maps internally to subsurface.formation_top, but
    that mapping lives in the resolver layer, never in this contract)."""

    FIELD = "field"
    DISCOVERY = "discovery"
    COMPANY = "company"
    LICENCE = "licence"
    FORMATIONS = "formations"
    STRATIGRAPHY = "stratigraphy"
    WELL_HISTORY = "well_history"
    CASING = "casing"
    DST = "dst"
    MUD = "mud"
    CORE = "core"
    CUTTINGS = "cuttings"
    LOGS = "logs"


class OutputField(str, Enum):
    """A curated, semantic result vocabulary - deliberately not column or
    table names, so this contract stays decoupled from how any layer
    downstream actually stores the data."""

    SIMILARITY = "similarity"
    DEPTH_RANGE = "depth_range"
    CURVES_PRESENT = "curves_present"
    WELL_NAME = "well_name"
    FIELD_NAME = "field_name"
    OPERATOR = "operator"
    FORMATIONS = "formations"
    STRATIGRAPHIC_UNITS = "stratigraphic_units"
    WINDOWS_TOTAL = "windows_total"
    POOLING_FRACTION = "pooling_fraction"
    MATCH_METHOD = "match_method"


# Per-intent field applicability. A field not listed as required or
# optional for a given intent is FORBIDDEN for that intent - this is what
# makes "reject contradictory combinations" enforceable in one place.
_REQUIRED_FIELDS = {
    QueryIntent.SIMILAR_WELLS: {"target_dataset", "target_well_id"},
    QueryIntent.SIMILAR_WINDOWS: {"target_dataset", "target_well_id", "target_window_id"},
    QueryIntent.WELL_INFORMATION: {"target_dataset", "target_well_id"},
    QueryIntent.FORMATION_INFORMATION: {"target_dataset", "target_well_id"},
    QueryIntent.COMPARE_WELLS: {"target_dataset", "target_well_id", "comparison_dataset", "comparison_well_id"},
    QueryIntent.GEOLOGICAL_CONTEXT: {"target_dataset", "target_well_id"},
    QueryIntent.DOCUMENT_SEARCH: {"search_text"},
}

# Fields that let ANY well/SODIR intent additionally pull in document
# evidence alongside its normal results ("combined" queries) - see
# docs/document_retrieval.md. document_search itself is document-only and
# does not use this set (it has its own optional fields below).
_DOCUMENT_AUGMENTATION_FIELDS = {"search_text", "document_source_type", "document_file_name"}

_OPTIONAL_FIELDS = {
    QueryIntent.SIMILAR_WELLS: {"top_k", "dataset_filter", "requested_output_fields",
                                 "requested_geological_context"} | _DOCUMENT_AUGMENTATION_FIELDS,
    QueryIntent.SIMILAR_WINDOWS: {"top_k", "dataset_filter", "min_curves_present", "requested_output_fields",
                                   "requested_geological_context"} | _DOCUMENT_AUGMENTATION_FIELDS,
    QueryIntent.WELL_INFORMATION: {"requested_geological_context",
                                    "requested_output_fields"} | _DOCUMENT_AUGMENTATION_FIELDS,
    QueryIntent.FORMATION_INFORMATION: {"requested_geological_context",
                                         "requested_output_fields"} | _DOCUMENT_AUGMENTATION_FIELDS,
    QueryIntent.COMPARE_WELLS: {"requested_geological_context",
                                 "requested_output_fields"} | _DOCUMENT_AUGMENTATION_FIELDS,
    QueryIntent.GEOLOGICAL_CONTEXT: {"requested_geological_context",
                                      "requested_output_fields"} | _DOCUMENT_AUGMENTATION_FIELDS,
    QueryIntent.DOCUMENT_SEARCH: {"top_k", "document_source_type", "document_file_name"},
}

# Every optional/settable field on the model, for computing "forbidden" as
# the complement of required|optional per intent.
_ALL_SETTABLE_FIELDS = {
    "target_dataset", "target_well_id", "target_window_id", "top_k",
    "dataset_filter", "min_curves_present", "comparison_dataset",
    "comparison_well_id", "requested_geological_context", "requested_output_fields",
    "search_text", "document_source_type", "document_file_name",
}


class StructuredQuery(BaseModel):
    """The structured query contract. Small, flat, and deterministic by
    design: every field is a primitive, an enum, or a list of enums - never
    a string of SQL, a table name, or free-form code. Unknown fields are
    rejected outright (extra='forbid')."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    intent: QueryIntent

    # --- reference to the primary target (well and/or window) ---
    target_dataset: Optional[DatasetEnum] = None
    target_well_id: Optional[str] = Field(default=None, max_length=WELL_ID_MAX_LENGTH, pattern=WELL_ID_PATTERN)
    target_window_id: Optional[int] = Field(default=None, ge=0)

    # --- retrieval controls ---
    top_k: Optional[int] = Field(default=None, ge=TOP_K_MIN, le=TOP_K_MAX)
    dataset_filter: Optional[DatasetEnum] = None
    min_curves_present: Optional[int] = Field(default=None, ge=0, le=MAX_SHARED_CURVES)

    # --- second well, needed only by compare_wells (see module docstring:
    # added beyond the literal field list because compare_wells cannot be
    # expressed with only one well reference) ---
    comparison_dataset: Optional[DatasetEnum] = None
    comparison_well_id: Optional[str] = Field(default=None, max_length=WELL_ID_MAX_LENGTH, pattern=WELL_ID_PATTERN)

    # --- geological context / output shaping ---
    requested_geological_context: Optional[List[GeologicalContextField]] = None
    requested_output_fields: Optional[List[OutputField]] = None

    # --- document retrieval (384-dim sentence-transformer space - kept
    # entirely separate from the 30-dim well/window embedding fields
    # above). Settable on document_search (document-only) or, optionally,
    # on any well/SODIR intent to additionally pull in document evidence
    # for a "combined" query. See docs/document_retrieval.md. ---
    search_text: Optional[str] = Field(default=None, max_length=SEARCH_TEXT_MAX_LENGTH)
    document_source_type: Optional[DocumentSourceType] = None
    document_file_name: Optional[str] = Field(
        default=None, max_length=DOCUMENT_FILE_NAME_MAX_LENGTH, pattern=DOCUMENT_FILE_NAME_PATTERN
    )

    @model_validator(mode="after")
    def _check_intent_field_applicability(self) -> "StructuredQuery":
        required = _REQUIRED_FIELDS[self.intent]
        optional = _OPTIONAL_FIELDS[self.intent]
        allowed = required | optional
        forbidden = _ALL_SETTABLE_FIELDS - allowed

        missing = [f for f in required if getattr(self, f) is None]
        if missing:
            raise ValueError(
                f"intent '{self.intent.value}' requires field(s) {sorted(missing)} to be set"
            )

        present_forbidden = [f for f in forbidden if getattr(self, f) is not None]
        if present_forbidden:
            raise ValueError(
                f"intent '{self.intent.value}' does not accept field(s) {sorted(present_forbidden)} "
                f"- contradictory combination"
            )

        return self

    @model_validator(mode="after")
    def _check_compare_wells_not_self(self) -> "StructuredQuery":
        if self.intent != QueryIntent.COMPARE_WELLS:
            return self
        if (
            self.target_dataset == self.comparison_dataset
            and self.target_well_id == self.comparison_well_id
        ):
            raise ValueError(
                "compare_wells target and comparison well must not be the same "
                "(dataset, well_id) - comparing a well to itself is not a valid comparison"
            )
        return self
