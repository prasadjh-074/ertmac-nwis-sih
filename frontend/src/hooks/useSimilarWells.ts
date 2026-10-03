import { useQuery } from "@tanstack/react-query";
import { getSimilarWells } from "@/api/wells";
import type { WellRef } from "@/api/types";

export function useSimilarWells(ref: WellRef | null, topK = 10, datasetFilter?: string) {
  return useQuery({
    queryKey: ["wells", "similar", ref?.dataset, ref?.well_id, topK, datasetFilter ?? null],
    queryFn: () => getSimilarWells(ref!, topK, datasetFilter),
    enabled: !!ref,
  });
}
