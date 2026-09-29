"""Deterministic evidence fusion.

Transforms raw EvidenceItem list from the graph's collect_evidence node
into a FusedEvidence structure with deduplication, grouping, provenance,
conflict detection, and missing-information tracking. No LLM is used.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from graph.state import EvidenceItem
from resolver.models import ResolutionResult

from .models import (
    EvidenceGroup,
    FusedEvidence,
    FusedEvidenceItem,
    MissingInfo,
    SourceDifference,
)
from .provenance import build_provenance, collect_source_systems, get_source_type


def fuse_evidence(
    evidence: List[EvidenceItem],
    resolution_result: Optional[ResolutionResult] = None,
    intent: Optional[str] = None,
) -> FusedEvidence:
    if not evidence:
        if intent == "document_search":
            missing = [MissingInfo(
                info_type="no_documents_found",
                description="No matching document chunks were found for this search",
                reason="not_available",
            )]
        else:
            missing = _detect_missing(resolution_result, intent)
        return FusedEvidence(missing=missing)

    fused_items = _build_fused_items(evidence)
    fused_items = _deduplicate(fused_items)

    groups = _group_by_entity(fused_items)
    differences = _detect_differences(fused_items)
    missing = _detect_missing(resolution_result, intent)
    source_systems = collect_source_systems(evidence)

    return FusedEvidence(
        items=fused_items,
        groups=groups,
        differences=differences,
        missing=missing,
        source_systems=source_systems,
        item_count=len(fused_items),
    )


def _build_fused_items(evidence: List[EvidenceItem]) -> List[FusedEvidenceItem]:
    items = []
    for i, ev in enumerate(evidence):
        prov = build_provenance(ev)
        source_type = get_source_type(ev.entity_type)

        explanation = None
        if source_type == "document":
            fname = ev.metadata.get("file_name", "unknown file")
            page = ev.metadata.get("page_number")
            loc = f", page {page}" if page is not None else ""
            sim_str = f", cosine similarity: {ev.similarity:.3f}" if ev.similarity is not None else ""
            explanation = f"Matched chunk in {fname}{loc}{sim_str}"
        elif ev.similarity is not None:
            explanation = f"Cosine similarity: {ev.similarity:.3f}"
        elif ev.entity_type == "well_info":
            sodir_id = ev.source_id
            if sodir_id:
                explanation = f"Linked to SODIR wellbore {sodir_id}"
            else:
                explanation = "No SODIR identity link available"
        elif ev.entity_type == "formation":
            name = ev.metadata.get("formation_name", "unknown")
            explanation = f"Formation top: {name}"

        relevance = None
        if ev.similarity is not None:
            if ev.similarity >= 0.9:
                relevance = "high"
            elif ev.similarity >= 0.7:
                relevance = "moderate"
            else:
                relevance = "low"
        elif source_type in ("wellbore_record", "formation_top", "field_record",
                             "company_record", "discovery_record", "licence_record"):
            relevance = "direct"

        items.append(FusedEvidenceItem(
            evidence_id=f"ev-{i:03d}",
            source_system=ev.source_system,
            source_type=source_type,
            entity_type=ev.entity_type,
            well_id=ev.well_id,
            source_id=ev.source_id,
            similarity=ev.similarity,
            value=ev.metadata if ev.metadata else None,
            relevance=relevance,
            provenance=prov,
            explanation=explanation,
        ))
    return items


def _deduplicate(items: List[FusedEvidenceItem]) -> List[FusedEvidenceItem]:
    seen: Set[Tuple] = set()
    result = []
    for item in items:
        key = (item.source_system, item.entity_type, item.well_id, item.source_id, item.similarity)
        if key not in seen:
            seen.add(key)
            result.append(item)
    for i, item in enumerate(result):
        item.evidence_id = f"ev-{i:03d}"
    return result


def _group_by_entity(items: List[FusedEvidenceItem]) -> List[EvidenceGroup]:
    groups_dict: Dict[str, List[FusedEvidenceItem]] = {}
    for item in items:
        key = item.entity_type
        groups_dict.setdefault(key, []).append(item)

    groups = []
    for entity_type, group_items in groups_dict.items():
        systems = list(dict.fromkeys(i.source_system for i in group_items))
        groups.append(EvidenceGroup(
            group_key=entity_type,
            entity_type=entity_type,
            items=group_items,
            source_systems=systems,
        ))
    return groups


def _detect_differences(items: List[FusedEvidenceItem]) -> List[SourceDifference]:
    diffs: List[SourceDifference] = []
    by_well: Dict[str, List[FusedEvidenceItem]] = {}
    for item in items:
        if item.well_id:
            by_well.setdefault(item.well_id, []).append(item)

    for well_id, well_items in by_well.items():
        systems = {i.source_system for i in well_items}
        if len(systems) < 2:
            continue

        field_values: Dict[str, Dict[str, set]] = {}
        for item in well_items:
            if not isinstance(item.value, dict):
                continue
            for field_name, val in item.value.items():
                if val is None:
                    continue
                field_values.setdefault(field_name, {}).setdefault(item.source_system, set()).add(str(val))

        for field_name, sys_vals in field_values.items():
            if len(sys_vals) < 2:
                continue
            all_value_sets = list(sys_vals.values())
            all_same = all(s == all_value_sets[0] for s in all_value_sets[1:])
            if all_same:
                continue

            sys_list = list(sys_vals.items())
            for i in range(len(sys_list)):
                for j in range(i + 1, len(sys_list)):
                    sa, va = sys_list[i]
                    sb, vb = sys_list[j]
                    if va != vb:
                        diffs.append(SourceDifference(
                            difference_type="source_difference",
                            field_name=field_name,
                            source_a=sa,
                            value_a=sorted(va),
                            source_b=sb,
                            value_b=sorted(vb),
                        ))
    return diffs


def _detect_missing(
    resolution_result: Optional[ResolutionResult],
    intent: Optional[str],
) -> List[MissingInfo]:
    missing: List[MissingInfo] = []

    if intent == "document_search":
        # document_search never produces a ResolutionResult by design -
        # its own evidence-presence check happens in fuse_evidence()'s
        # empty-evidence branch above, not here.
        return missing

    if resolution_result is None:
        missing.append(MissingInfo(
            info_type="no_resolution",
            description="No resolution result available",
            reason="not_resolved",
        ))
        return missing

    if resolution_result.status == "not_found":
        missing.append(MissingInfo(
            info_type="not_found",
            description="The requested entity was not found in any data source",
            reason="not_found",
        ))

    if resolution_result.status == "partial":
        missing.append(MissingInfo(
            info_type="partial_data",
            description="Some requested information was unavailable",
            reason="not_linked",
        ))

    meta = resolution_result.metadata or {}
    if meta.get("sodir_linked") is False or (
        isinstance(resolution_result.results, dict)
        and not resolution_result.results.get("sodir_wellbore_id")
    ):
        missing.append(MissingInfo(
            info_type="no_sodir_link",
            description="Well has no SODIR identity link",
            reason="not_linked",
        ))

    if intent == "formation_information" and resolution_result.result_count == 0:
        missing.append(MissingInfo(
            info_type="no_formations",
            description="No formation tops found for this well",
            reason="not_available",
        ))

    return missing
