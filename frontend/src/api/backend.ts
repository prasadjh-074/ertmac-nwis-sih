/**
 * Typed wrappers for every FastAPI endpoint (see docs/backend_api.md).
 *
 * All calls go through the shared apiGet/apiPost from src/lib/api.ts,
 * which routes through /api (Vite dev proxy → uvicorn on 8000).
 * Nothing here reaches out to a third-party service — the frontend
 * only talks to the FastAPI backend.
 */

import { apiGet, apiPost } from "@/lib/api";
import type {
  APIErrorBody,
  AlertListResponse,
  ContextResponse,
  CorrelatedEventListResponse,
  CurrentWellStateResponse,
  DocumentMetadataResponse,
  DocumentSearchResponse,
  EventListResponse,
  HealthResponse,
  NearbyWellListResponse,
  QueryResponseBody,
  RiskAssessResponse,
  SimilarWellListResponse,
  WellListResponse,
  WellLocationResponse,
} from "./backend-types";

// ── Utilities ────────────────────────────────────────────────

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

/** Backend error envelope narrowing — surfaces the structured error
 *  from api/errors.py so hooks can render `message`, `request_id`,
 *  and `type` uniformly. */
export function extractBackendError(err: unknown): { type: string; message: string; requestId: string | null; status: number } | null {
  if (!err || typeof err !== "object") return null;
  const anyErr = err as { name?: string; status?: number; body?: unknown };
  if (anyErr.name !== "ApiError") return null;
  const body = anyErr.body as Partial<APIErrorBody> | null | undefined;
  const inner = body?.error;
  if (!inner || typeof inner !== "object") {
    // Response wasn't our structured JSON envelope at all — typically
    // the Vite dev proxy's own error page when it can't reach the
    // backend (connection refused), not something api/errors.py
    // produced. Confirmed live: killing the backend makes this the
    // path that actually renders, not the network-level fetch-throw
    // one — so this message, not a generic one, is what a demoer sees.
    return {
      type: "unknown",
      message: "Request failed — the backend at http://127.0.0.1:8000 may be unreachable.",
      requestId: null,
      status: anyErr.status ?? 0,
    };
  }
  return {
    type: inner.type ?? "unknown",
    message: inner.message ?? "Request failed.",
    requestId: inner.request_id ?? null,
    status: inner.status ?? anyErr.status ?? 0,
  };
}

// ── Health ───────────────────────────────────────────────────
export const fetchHealth = () => apiGet<HealthResponse>("/health");

// ── Wells ────────────────────────────────────────────────────
export const fetchWells = (params: { dataset?: string; limit?: number } = {}) =>
  apiGet<WellListResponse>(`/wells${qs(params)}`);

export const fetchWellLookup = (params: { dataset: string; well_id: string }) =>
  apiGet<WellLocationResponse>(`/wells/lookup${qs(params)}`);

export const fetchNearbyWells = (params: {
  dataset: string;
  well_id: string;
  radius_km?: number;
  limit?: number;
  dataset_filter?: string;
}) => apiGet<NearbyWellListResponse>(`/wells/nearby${qs(params)}`);

export const fetchSimilarWells = (params: {
  dataset: string;
  well_id: string;
  top_k?: number;
  dataset_filter?: string;
}) => apiGet<SimilarWellListResponse>(`/wells/similar${qs(params)}`);

export const fetchWellContext = (params: {
  dataset: string;
  well_id: string;
  radius_km?: number;
  nearby_limit?: number;
  similar_limit?: number;
}) => apiGet<ContextResponse>(`/wells/context${qs(params)}`);

export const fetchWellState = (params: { dataset: string; well_id: string }) =>
  apiGet<CurrentWellStateResponse>(`/wells/state${qs(params)}`);

// ── Events ───────────────────────────────────────────────────
export const fetchEventsForWell = (params: {
  dataset: string;
  well_id: string;
  event_type?: string;
}) => apiGet<EventListResponse>(`/events/well${qs(params)}`);

export const fetchEventsNearDepth = (params: {
  dataset: string;
  well_id: string;
  depth_m: number;
  tolerance_m?: number;
  event_type?: string;
}) => apiGet<EventListResponse>(`/events/near-depth${qs(params)}`);

export const fetchEventsByFormation = (params: {
  formation: string;
  dataset?: string;
  well_id?: string;
  event_type?: string;
}) => apiGet<EventListResponse>(`/events/formation${qs(params)}`);

export const fetchCorrelatedEvents = (params: {
  dataset: string;
  well_id: string;
  current_depth_m?: number;
  current_formation?: string;
  radius_km?: number;
  limit?: number;
  event_type?: string;
}) => apiGet<CorrelatedEventListResponse>(`/events/correlated${qs(params)}`);

// ── Risk ─────────────────────────────────────────────────────
export const fetchRiskAssess = (params: {
  dataset: string;
  well_id: string;
  current_depth_m?: number;
  current_formation?: string;
  radius_km?: number;
  limit?: number;
}) => apiGet<RiskAssessResponse>(`/risk/assess${qs(params)}`);

export const fetchRiskAlerts = (params: {
  dataset: string;
  well_id: string;
  current_depth_m?: number;
  current_formation?: string;
  radius_km?: number;
  limit?: number;
}) => apiGet<AlertListResponse>(`/risk/alerts${qs(params)}`);

// ── Query / AI intelligence ──────────────────────────────────
export const askNaturalLanguage = (question: string) =>
  apiPost<QueryResponseBody>("/query", { question });

export const askStructured = (structured_query: Record<string, unknown>) =>
  apiPost<QueryResponseBody>("/query/structured", { structured_query });

// ── Documents ────────────────────────────────────────────────
export const searchDocuments = (body: {
  query: string;
  top_k?: number;
  source_type?: string;
  file_name?: string;
}) => apiPost<DocumentSearchResponse>("/documents/search", body);

export const fetchDocumentMetadata = (document_id: string) =>
  apiGet<DocumentMetadataResponse>(`/documents/${document_id}`);
