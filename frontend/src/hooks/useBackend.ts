/**
 * TanStack Query hooks for every FastAPI backend endpoint.
 *
 * One hook per endpoint; each key is stable and derived from its
 * params so cache invalidation is predictable. Hooks are disabled
 * when required identifiers are missing (`enabled: !!well_id`) so
 * that we never emit a request the backend will 422 on.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  askNaturalLanguage,
  askStructured,
  fetchCorrelatedEvents,
  fetchDocumentMetadata,
  fetchEventsForWell,
  fetchEventsNearDepth,
  fetchHealth,
  fetchNearbyWells,
  fetchRiskAlerts,
  fetchRiskAssess,
  fetchSimilarWells,
  fetchWellContext,
  fetchWellLookup,
  fetchWellState,
  fetchWells,
  searchDocuments,
} from "@/api/backend";

// ── Health ───────────────────────────────────────────────────
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: false,
    staleTime: 15_000,
  });
}

// ── Wells ────────────────────────────────────────────────────
export function useWells(params: { dataset?: string; limit?: number } = {}) {
  return useQuery({
    queryKey: ["wells", params],
    queryFn: () => fetchWells(params),
    staleTime: 60_000,
    retry: false,
  });
}

export function useWellLookup(dataset: string | null, wellId: string | null) {
  return useQuery({
    queryKey: ["well-lookup", dataset, wellId],
    queryFn: () => fetchWellLookup({ dataset: dataset as string, well_id: wellId as string }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 60_000,
  });
}

export function useNearbyWells(
  dataset: string | null,
  wellId: string | null,
  radius_km = 50,
  limit = 10,
) {
  return useQuery({
    queryKey: ["nearby-wells", dataset, wellId, radius_km, limit],
    queryFn: () =>
      fetchNearbyWells({ dataset: dataset as string, well_id: wellId as string, radius_km, limit }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 60_000,
  });
}

export function useSimilarWells(dataset: string | null, wellId: string | null, top_k = 10) {
  return useQuery({
    queryKey: ["similar-wells", dataset, wellId, top_k],
    queryFn: () => fetchSimilarWells({ dataset: dataset as string, well_id: wellId as string, top_k }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 60_000,
  });
}

export function useWellContext(dataset: string | null, wellId: string | null) {
  return useQuery({
    queryKey: ["well-context", dataset, wellId],
    queryFn: () => fetchWellContext({ dataset: dataset as string, well_id: wellId as string }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 60_000,
  });
}

export function useWellState(dataset: string | null, wellId: string | null) {
  return useQuery({
    queryKey: ["well-state", dataset, wellId],
    queryFn: () => fetchWellState({ dataset: dataset as string, well_id: wellId as string }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 30_000,
  });
}

// ── Events ───────────────────────────────────────────────────
export function useEventsForWell(dataset: string | null, wellId: string | null, event_type?: string) {
  return useQuery({
    queryKey: ["events-well", dataset, wellId, event_type ?? null],
    queryFn: () =>
      fetchEventsForWell({ dataset: dataset as string, well_id: wellId as string, event_type }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 60_000,
  });
}

export function useEventsNearDepth(
  dataset: string | null,
  wellId: string | null,
  depth_m: number | null,
  tolerance_m = 100,
) {
  return useQuery({
    queryKey: ["events-near-depth", dataset, wellId, depth_m, tolerance_m],
    queryFn: () =>
      fetchEventsNearDepth({
        dataset: dataset as string,
        well_id: wellId as string,
        depth_m: depth_m as number,
        tolerance_m,
      }),
    enabled: !!dataset && !!wellId && depth_m !== null,
    retry: false,
    staleTime: 60_000,
  });
}

export function useCorrelatedEvents(
  dataset: string | null,
  wellId: string | null,
  current_depth_m: number | null | undefined = undefined,
  current_formation: string | null | undefined = undefined,
  radius_km = 50,
  limit = 20,
) {
  return useQuery({
    queryKey: [
      "correlated-events",
      dataset,
      wellId,
      current_depth_m ?? null,
      current_formation ?? null,
      radius_km,
      limit,
    ],
    queryFn: () =>
      fetchCorrelatedEvents({
        dataset: dataset as string,
        well_id: wellId as string,
        current_depth_m: current_depth_m ?? undefined,
        current_formation: current_formation ?? undefined,
        radius_km,
        limit,
      }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 60_000,
  });
}

// ── Risk ─────────────────────────────────────────────────────
export function useRiskAssess(
  dataset: string | null,
  wellId: string | null,
  current_depth_m: number | null | undefined = undefined,
  current_formation: string | null | undefined = undefined,
) {
  return useQuery({
    queryKey: ["risk-assess", dataset, wellId, current_depth_m ?? null, current_formation ?? null],
    queryFn: () =>
      fetchRiskAssess({
        dataset: dataset as string,
        well_id: wellId as string,
        current_depth_m: current_depth_m ?? undefined,
        current_formation: current_formation ?? undefined,
      }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 15_000,
  });
}

export function useRiskAlerts(
  dataset: string | null,
  wellId: string | null,
  current_depth_m: number | null | undefined = undefined,
  current_formation: string | null | undefined = undefined,
) {
  return useQuery({
    queryKey: ["risk-alerts", dataset, wellId, current_depth_m ?? null, current_formation ?? null],
    queryFn: () =>
      fetchRiskAlerts({
        dataset: dataset as string,
        well_id: wellId as string,
        current_depth_m: current_depth_m ?? undefined,
        current_formation: current_formation ?? undefined,
      }),
    enabled: !!dataset && !!wellId,
    retry: false,
    staleTime: 15_000,
  });
}

// ── Query (natural-language + structured) ────────────────────
export function useAskNaturalLanguage() {
  return useMutation({
    mutationFn: (question: string) => askNaturalLanguage(question),
  });
}

export function useAskStructured() {
  return useMutation({
    mutationFn: (structured_query: Record<string, unknown>) => askStructured(structured_query),
  });
}

// ── Documents ────────────────────────────────────────────────
export function useDocumentSearch() {
  return useMutation({
    mutationFn: (body: { query: string; top_k?: number; source_type?: string; file_name?: string }) =>
      searchDocuments(body),
  });
}

export function useDocumentMetadata(document_id: string | null) {
  return useQuery({
    queryKey: ["document-metadata", document_id],
    queryFn: () => fetchDocumentMetadata(document_id as string),
    enabled: !!document_id,
    retry: false,
    staleTime: 60_000,
  });
}
