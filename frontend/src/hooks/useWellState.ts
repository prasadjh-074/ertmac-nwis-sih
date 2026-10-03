import { useQuery } from "@tanstack/react-query";
import { getWellState } from "@/api/wells";
import type { WellRef } from "@/api/types";
import { useWorkspace } from "@/state/WorkspaceContext";

export function useWellState(ref: WellRef | null) {
  return useQuery({
    queryKey: ["wells", "state", ref?.dataset, ref?.well_id],
    queryFn: () => getWellState(ref!),
    enabled: !!ref,
    staleTime: 60_000,
  });
}

// Parameters every risk/correlation call shares: backend state, optionally overridden by the engineer.
export function useAssessmentParams() {
  const { currentWell, depthOverride, formationOverride, radiusKm } = useWorkspace();
  const state = useWellState(currentWell);
  const depth = depthOverride ?? state.data?.current_depth_m ?? null;
  const formation = formationOverride.trim() || state.data?.current_formation || null;
  return {
    ref: currentWell,
    depth,
    formation,
    radiusKm,
    depthSource: depthOverride != null ? ("engineer" as const) : state.data?.current_depth_m != null ? ("backend" as const) : null,
    ready: !!currentWell && (state.isSuccess || state.isError),
  };
}
