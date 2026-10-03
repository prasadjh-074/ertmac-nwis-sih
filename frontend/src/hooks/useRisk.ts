import { useQuery } from "@tanstack/react-query";
import { assessRisk } from "@/api/risk";
import type { WellRef } from "@/api/types";
import { useAssessmentParams } from "./useWellState";

export function useRiskAssessment() {
  const p = useAssessmentParams();
  return useQuery({
    queryKey: ["risk", "assess", p.ref?.dataset, p.ref?.well_id, p.depth, p.formation, p.radiusKm],
    queryFn: () => assessRisk(p.ref!, { current_depth_m: p.depth, current_formation: p.formation, radius_km: p.radiusKm }),
    enabled: p.ready,
  });
}

// Offset-well quick look (no depth context): used by the well detail panel.
export function useWellRiskSnapshot(ref: WellRef | null) {
  return useQuery({
    queryKey: ["risk", "assess", ref?.dataset, ref?.well_id, null, null, 50],
    queryFn: () => assessRisk(ref!, { radius_km: 50 }),
    enabled: !!ref,
  });
}
