"""
Query resolver: StructuredQuery → deterministic data retrieval.

Maps each of the 6 intents to the appropriate combination of:
- retrieval/ (pgvector cosine similarity for similar_wells/similar_windows)
- core.*/subsurface.*/graph.* (SODIR relational data for info/context intents)

No LLM, no generated SQL, no invented data. Every SQL query uses
parameterized placeholders.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import psycopg2

from query.schema import QueryIntent, StructuredQuery
from retrieval.hybrid_search import search_similar_wells_by_id, search_similar_windows_by_id
from retrieval.vector_search import get_connection, fetch_well_vector
from retrieval.ranking import WellResult, WindowResult

from .errors import EntityNotFoundError, QueryResolutionError, ResolverDataError, UnsupportedIntentError
from .models import (
    CompanyRole,
    CompareWellsResult,
    FormationTop,
    GeologicalContextGroup,
    ResolutionResult,
    WellInfo,
    WellMatch,
    WindowMatch,
)

logger = logging.getLogger(__name__)

_INTENT_DISPATCH = {}


def _handles(intent: QueryIntent):
    def decorator(fn):
        _INTENT_DISPATCH[intent] = fn
        return fn
    return decorator


@dataclass
class QueryResolver:
    """Deterministic resolver: StructuredQuery → ResolutionResult."""

    _conn: Optional[Any] = field(default=None, repr=False)

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = get_connection()
        return self._conn

    def close(self):
        if self._conn is not None and not self._conn.closed:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def resolve(self, query: StructuredQuery) -> ResolutionResult:
        handler = _INTENT_DISPATCH.get(query.intent)
        if handler is None:
            raise UnsupportedIntentError(query.intent.value if hasattr(query.intent, 'value') else str(query.intent))
        try:
            return handler(self, query)
        except (EntityNotFoundError, UnsupportedIntentError):
            raise
        except QueryResolutionError:
            raise
        except LookupError as exc:
            raise EntityNotFoundError("well_or_window", str(exc)) from exc
        except psycopg2.Error as exc:
            raise ResolverDataError(f"Database error: {exc}", cause=exc) from exc

    # ------------------------------------------------------------------
    # SODIR helpers (parameterized SQL only)
    # ------------------------------------------------------------------

    def _resolve_wellbore_id(self, dataset: str, well_id: str, conn) -> Optional[int]:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT wellbore_id FROM graph.well_identity_link "
                "WHERE dataset = %s AND well_id = %s",
                (dataset, well_id),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def _fetch_well_info(self, dataset: str, well_id: str, conn) -> WellInfo:
        wellbore_id = self._resolve_wellbore_id(dataset, well_id, conn)

        info = WellInfo(dataset=dataset, well_id=well_id, source_system=dataset)

        if wellbore_id is None:
            return info

        with conn.cursor() as cur:
            # Match method from identity link
            cur.execute(
                "SELECT match_method, matched_sodir_name FROM graph.well_identity_link "
                "WHERE dataset = %s AND well_id = %s",
                (dataset, well_id),
            )
            link_row = cur.fetchone()
            if link_row:
                info.match_method = link_row[0]
                info.sodir_wellbore_name = link_row[1]

            # Wellbore metadata
            cur.execute(
                "SELECT wb.wellbore_id, wb.wellbore_name, wb.wellbore_type, wb.purpose, "
                "       wb.status, wb.operator, wb.field_id, wb.discovery_id, "
                "       wb.production_licence_id, wb.total_depth_m, wb.water_depth_m, "
                "       wb.spud_date, wb.completion_date "
                "FROM core.wellbore wb WHERE wb.wellbore_id = %s",
                (wellbore_id,),
            )
            wb = cur.fetchone()
            if wb is None:
                info.sodir_wellbore_id = wellbore_id
                return info

            info.sodir_wellbore_id = wb[0]
            info.sodir_wellbore_name = info.sodir_wellbore_name or wb[1]
            info.wellbore_type = wb[2]
            info.purpose = wb[3]
            info.status = wb[4]
            info.operator = wb[5]
            field_id = wb[6]
            discovery_id = wb[7]
            licence_id = wb[8]
            info.total_depth_m = float(wb[9]) if wb[9] is not None else None
            info.water_depth_m = float(wb[10]) if wb[10] is not None else None
            info.spud_date = str(wb[11]) if wb[11] is not None else None
            info.completion_date = str(wb[12]) if wb[12] is not None else None

            # Field
            if field_id is not None:
                cur.execute("SELECT field_name FROM core.field WHERE field_id = %s", (field_id,))
                fr = cur.fetchone()
                if fr:
                    info.field_name = fr[0]
                    info.field_id = field_id

            # Discovery
            if discovery_id is not None:
                cur.execute("SELECT discovery_name FROM core.discovery WHERE discovery_id = %s", (discovery_id,))
                dr = cur.fetchone()
                if dr:
                    info.discovery_name = dr[0]
                    info.discovery_id = discovery_id

            # Licence
            if licence_id is not None:
                cur.execute("SELECT licence_name FROM core.production_licence WHERE licence_id = %s", (licence_id,))
                lr = cur.fetchone()
                if lr:
                    info.licence_name = lr[0]
                    info.licence_id = licence_id

            # Companies
            cur.execute(
                "SELECT c.company_name, wc.role "
                "FROM core.wellbore_company wc "
                "JOIN core.company c ON c.company_id = wc.company_id "
                "WHERE wc.wellbore_id = %s ORDER BY wc.role, c.company_name",
                (wellbore_id,),
            )
            info.companies = [CompanyRole(company_name=r[0], role=r[1]) for r in cur.fetchall()]

        info.source_system = "SODIR" if wellbore_id else dataset
        return info

    def _fetch_formation_tops(self, wellbore_id: int, conn) -> List[FormationTop]:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ft.formation_id, ft.formation_name_normalized, "
                "       ft.top_depth_m, ft.base_depth_m, "
                "       f.formation_name, f.stratigraphic_age, "
                "       pf.formation_name AS parent_name "
                "FROM subsurface.formation_top ft "
                "LEFT JOIN subsurface.formation f ON f.formation_id = ft.formation_id "
                "LEFT JOIN subsurface.formation pf ON pf.formation_id = f.parent_formation_id "
                "WHERE ft.wellbore_id = %s "
                "ORDER BY ft.top_depth_m NULLS LAST",
                (wellbore_id,),
            )
            results = []
            for row in cur.fetchall():
                results.append(FormationTop(
                    formation_id=row[0],
                    formation_name=row[4] or row[1],
                    top_depth_m=float(row[2]) if row[2] is not None else None,
                    base_depth_m=float(row[3]) if row[3] is not None else None,
                    stratigraphic_age=row[5],
                    parent_formation_name=row[6],
                ))
            return results

    def _fetch_geological_context(self, wellbore_id: int, requested: List[str], conn) -> List[GeologicalContextGroup]:
        groups = []

        _TABLE_MAP = {
            "well_history": ("subsurface.wellbore_history", "wellbore_id",
                             ["history_id", "history_text", "history_date"]),
            "casing": ("subsurface.casing", "wellbore_id",
                       ["casing_id", "casing_type", "casing_diameter", "casing_depth_m",
                        "hole_diameter", "hole_depth_m"]),
            "dst": ("subsurface.dst", "wellbore_id",
                    ["dst_id", "test_number", "from_depth_m", "to_depth_m",
                     "final_shut_in_pressure", "final_flow_pressure",
                     "oil_production", "gas_production"]),
            "mud": ("subsurface.mud", "wellbore_id",
                    ["mud_id", "md_m", "mud_weight", "mud_viscosity", "mud_type"]),
            "core": ("subsurface.core", "wellbore_id",
                     ["core_id", "core_number", "interval_top_m", "interval_bottom_m",
                      "total_core_length", "sample_available"]),
            "cuttings": ("subsurface.cuttings", "wellbore_id",
                         ["cuttings_id", "top_depth_m", "bottom_depth_m", "sample_available"]),
            "logs": ("subsurface.log_curve", "wellbore_id",
                     ["curve_id", "curve_name_normalized", "unit", "measurement_type",
                      "depth_min_m", "depth_max_m", "sample_count"]),
        }

        for ctx_field in requested:
            if ctx_field == "formations":
                tops = self._fetch_formation_tops(wellbore_id, conn)
                groups.append(GeologicalContextGroup(
                    entity_type="formations",
                    records=[t.model_dump() for t in tops],
                    record_count=len(tops),
                ))
            elif ctx_field == "stratigraphy":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT f.formation_id, f.formation_name, f.stratigraphic_age, "
                        "       pf.formation_name AS parent_name "
                        "FROM subsurface.formation_top ft "
                        "JOIN subsurface.formation f ON f.formation_id = ft.formation_id "
                        "LEFT JOIN subsurface.formation pf ON pf.formation_id = f.parent_formation_id "
                        "WHERE ft.wellbore_id = %s "
                        "ORDER BY f.formation_name",
                        (wellbore_id,),
                    )
                    records = [
                        {"formation_id": r[0], "formation_name": r[1],
                         "stratigraphic_age": r[2], "parent_formation_name": r[3]}
                        for r in cur.fetchall()
                    ]
                groups.append(GeologicalContextGroup(
                    entity_type="stratigraphy", records=records, record_count=len(records),
                ))
            elif ctx_field == "field":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT f.field_id, f.field_name, f.operator, f.country "
                        "FROM core.field f "
                        "JOIN core.wellbore wb ON wb.field_id = f.field_id "
                        "WHERE wb.wellbore_id = %s",
                        (wellbore_id,),
                    )
                    records = [
                        {"field_id": r[0], "field_name": r[1], "operator": r[2], "country": r[3]}
                        for r in cur.fetchall()
                    ]
                groups.append(GeologicalContextGroup(
                    entity_type="field", records=records, record_count=len(records),
                ))
            elif ctx_field == "discovery":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT d.discovery_id, d.discovery_name, d.discovery_year, d.discovery_status "
                        "FROM core.discovery d "
                        "JOIN core.wellbore wb ON wb.discovery_id = d.discovery_id "
                        "WHERE wb.wellbore_id = %s",
                        (wellbore_id,),
                    )
                    records = [
                        {"discovery_id": r[0], "discovery_name": r[1],
                         "discovery_year": r[2], "discovery_status": r[3]}
                        for r in cur.fetchall()
                    ]
                groups.append(GeologicalContextGroup(
                    entity_type="discovery", records=records, record_count=len(records),
                ))
            elif ctx_field == "company":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT c.company_name, wc.role "
                        "FROM core.wellbore_company wc "
                        "JOIN core.company c ON c.company_id = wc.company_id "
                        "WHERE wc.wellbore_id = %s ORDER BY wc.role, c.company_name",
                        (wellbore_id,),
                    )
                    records = [{"company_name": r[0], "role": r[1]} for r in cur.fetchall()]
                groups.append(GeologicalContextGroup(
                    entity_type="company", records=records, record_count=len(records),
                ))
            elif ctx_field == "licence":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pl.licence_id, pl.licence_name, pl.licence_number, pl.status "
                        "FROM core.production_licence pl "
                        "JOIN core.wellbore wb ON wb.production_licence_id = pl.licence_id "
                        "WHERE wb.wellbore_id = %s",
                        (wellbore_id,),
                    )
                    records = [
                        {"licence_id": r[0], "licence_name": r[1],
                         "licence_number": r[2], "status": r[3]}
                        for r in cur.fetchall()
                    ]
                groups.append(GeologicalContextGroup(
                    entity_type="licence", records=records, record_count=len(records),
                ))
            elif ctx_field in _TABLE_MAP:
                table, fk_col, columns = _TABLE_MAP[ctx_field]
                col_list = ", ".join(columns)
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {col_list} FROM {table} WHERE {fk_col} = %s "
                        f"ORDER BY 1",
                        (wellbore_id,),
                    )
                    records = [dict(zip(columns, row)) for row in cur.fetchall()]
                groups.append(GeologicalContextGroup(
                    entity_type=ctx_field, records=records, record_count=len(records),
                ))

        return groups

    def _make_result(self, query: StructuredQuery, status: str, results: Any,
                     result_count: int, sources: List[str], **meta) -> ResolutionResult:
        return ResolutionResult(
            intent=query.intent.value,
            status=status,
            query=query.model_dump(exclude_none=True, mode="json"),
            results=results,
            result_count=result_count,
            sources=sources,
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    @_handles(QueryIntent.SIMILAR_WELLS)
    def _resolve_similar_wells(self, query: StructuredQuery) -> ResolutionResult:
        conn = self._get_conn()
        dataset = query.target_dataset.value
        well_id = query.target_well_id
        top_k = query.top_k or 10
        ds_filter = query.dataset_filter.value if query.dataset_filter else None

        results = search_similar_wells_by_id(
            dataset=dataset, well_id=well_id, top_k=top_k,
            dataset_filter=ds_filter, conn=conn,
        )

        matches = [
            WellMatch(
                dataset=r.dataset, well_id=r.well_id, similarity=r.similarity,
                rank=r.rank, windows_total=r.windows_total,
                windows_pooled=r.windows_pooled, pooling_fraction=r.pooling_fraction,
            )
            for r in results
        ]

        sources = sorted({m.dataset for m in matches}) if matches else [dataset]

        geo_context = None
        if query.requested_geological_context and matches:
            geo_context = {}
            for m in matches:
                wb_id = self._resolve_wellbore_id(m.dataset, m.well_id, conn)
                if wb_id is not None:
                    ctx_values = [g.value for g in query.requested_geological_context]
                    geo_context[f"{m.dataset}:{m.well_id}"] = [
                        g.model_dump() for g in
                        self._fetch_geological_context(wb_id, ctx_values, conn)
                    ]
                    if "SODIR" not in sources:
                        sources.append("SODIR")

        return self._make_result(
            query, "success",
            results=[m.model_dump() for m in matches],
            result_count=len(matches),
            sources=sources,
            query_well={"dataset": dataset, "well_id": well_id},
            geological_context=geo_context,
        )

    @_handles(QueryIntent.SIMILAR_WINDOWS)
    def _resolve_similar_windows(self, query: StructuredQuery) -> ResolutionResult:
        conn = self._get_conn()
        dataset = query.target_dataset.value
        well_id = query.target_well_id
        window_id = query.target_window_id
        top_k = query.top_k or 10
        ds_filter = query.dataset_filter.value if query.dataset_filter else None
        min_curves = query.min_curves_present

        results = search_similar_windows_by_id(
            dataset=dataset, well_id=well_id, window_id=window_id,
            top_k=top_k, dataset_filter=ds_filter,
            min_curves_present=min_curves, conn=conn,
        )

        matches = [
            WindowMatch(
                dataset=r.dataset, well_id=r.well_id, window_id=r.window_id,
                depth_start_m=r.depth_start_m, depth_end_m=r.depth_end_m,
                similarity=r.similarity, rank=r.rank, curves_present=r.curves_present,
            )
            for r in results
        ]

        sources = sorted({m.dataset for m in matches}) if matches else [dataset]

        return self._make_result(
            query, "success",
            results=[m.model_dump() for m in matches],
            result_count=len(matches),
            sources=sources,
            query_window={"dataset": dataset, "well_id": well_id, "window_id": window_id},
        )

    @_handles(QueryIntent.WELL_INFORMATION)
    def _resolve_well_information(self, query: StructuredQuery) -> ResolutionResult:
        conn = self._get_conn()
        dataset = query.target_dataset.value
        well_id = query.target_well_id

        info = self._fetch_well_info(dataset, well_id, conn)
        sources = [dataset]
        if info.sodir_wellbore_id is not None:
            sources.append("SODIR")

        geo_context = None
        if query.requested_geological_context and info.sodir_wellbore_id:
            ctx_values = [g.value for g in query.requested_geological_context]
            geo_context = [
                g.model_dump() for g in
                self._fetch_geological_context(info.sodir_wellbore_id, ctx_values, conn)
            ]

        return self._make_result(
            query,
            "success" if info.sodir_wellbore_id else "partial",
            results=info.model_dump(),
            result_count=1,
            sources=sources,
            geological_context=geo_context,
            sodir_linked=info.sodir_wellbore_id is not None,
        )

    @_handles(QueryIntent.FORMATION_INFORMATION)
    def _resolve_formation_information(self, query: StructuredQuery) -> ResolutionResult:
        conn = self._get_conn()
        dataset = query.target_dataset.value
        well_id = query.target_well_id

        wellbore_id = self._resolve_wellbore_id(dataset, well_id, conn)
        if wellbore_id is None:
            return self._make_result(
                query, "not_found",
                results=[],
                result_count=0,
                sources=[dataset],
                reason=f"No SODIR identity link for {dataset}:{well_id}",
            )

        tops = self._fetch_formation_tops(wellbore_id, conn)

        return self._make_result(
            query, "success",
            results=[t.model_dump() for t in tops],
            result_count=len(tops),
            sources=[dataset, "SODIR"],
            wellbore_id=wellbore_id,
        )

    @_handles(QueryIntent.COMPARE_WELLS)
    def _resolve_compare_wells(self, query: StructuredQuery) -> ResolutionResult:
        conn = self._get_conn()
        ds1 = query.target_dataset.value
        wid1 = query.target_well_id
        ds2 = query.comparison_dataset.value
        wid2 = query.comparison_well_id

        info1 = self._fetch_well_info(ds1, wid1, conn)
        info2 = self._fetch_well_info(ds2, wid2, conn)

        similarity = None
        try:
            vec1 = fetch_well_vector(ds1, wid1, conn=conn)
            vec2 = fetch_well_vector(ds2, wid2, conn=conn)
            dot = sum(a * b for a, b in zip(vec1, vec2))
            mag1 = sum(a * a for a in vec1) ** 0.5
            mag2 = sum(b * b for b in vec2) ** 0.5
            if mag1 > 0 and mag2 > 0:
                similarity = dot / (mag1 * mag2)
        except LookupError:
            pass

        comparison = CompareWellsResult(target=info1, comparison=info2, similarity=similarity)

        sources = sorted({ds1, ds2})
        if info1.sodir_wellbore_id or info2.sodir_wellbore_id:
            sources.append("SODIR")

        geo_context = None
        if query.requested_geological_context:
            geo_context = {}
            ctx_values = [g.value for g in query.requested_geological_context]
            for label, info in [("target", info1), ("comparison", info2)]:
                if info.sodir_wellbore_id:
                    geo_context[label] = [
                        g.model_dump() for g in
                        self._fetch_geological_context(info.sodir_wellbore_id, ctx_values, conn)
                    ]

        return self._make_result(
            query, "success",
            results=comparison.model_dump(),
            result_count=2,
            sources=sources,
            geological_context=geo_context,
        )

    @_handles(QueryIntent.GEOLOGICAL_CONTEXT)
    def _resolve_geological_context(self, query: StructuredQuery) -> ResolutionResult:
        conn = self._get_conn()
        dataset = query.target_dataset.value
        well_id = query.target_well_id

        wellbore_id = self._resolve_wellbore_id(dataset, well_id, conn)
        if wellbore_id is None:
            return self._make_result(
                query, "not_found",
                results=[],
                result_count=0,
                sources=[dataset],
                reason=f"No SODIR identity link for {dataset}:{well_id}",
            )

        ctx_values = [g.value for g in query.requested_geological_context] \
            if query.requested_geological_context else \
            ["field", "discovery", "company", "licence", "formations"]

        groups = self._fetch_geological_context(wellbore_id, ctx_values, conn)

        total_records = sum(g.record_count for g in groups)

        return self._make_result(
            query, "success",
            results=[g.model_dump() for g in groups],
            result_count=total_records,
            sources=[dataset, "SODIR"],
            wellbore_id=wellbore_id,
        )
