import { useQuery } from "@tanstack/react-query";
import { getWellContext } from "@/api/wells";
import type { WellRef } from "@/api/types";

export function useWellContext(ref: WellRef | null, radiusKm = 50) {
  return useQuery({
    queryKey: ["wells", "context", ref?.dataset, ref?.well_id, radiusKm],
    queryFn: () => getWellContext(ref!, radiusKm, 10, 10),
    enabled: !!ref,
  });
}
