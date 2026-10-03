import { useQuery } from "@tanstack/react-query";
import { getNearbyWells } from "@/api/wells";
import type { WellRef } from "@/api/types";

export function useNearbyWells(ref: WellRef | null, radiusKm: number, limit = 20, datasetFilter?: string) {
  return useQuery({
    queryKey: ["wells", "nearby", ref?.dataset, ref?.well_id, radiusKm, limit, datasetFilter ?? null],
    queryFn: () => getNearbyWells(ref!, radiusKm, limit, datasetFilter),
    enabled: !!ref,
  });
}
