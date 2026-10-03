import { useQuery } from "@tanstack/react-query";
import { getRiskAlerts } from "@/api/risk";
import { useAssessmentParams } from "./useWellState";

export function useRiskAlerts() {
  const p = useAssessmentParams();
  return useQuery({
    queryKey: ["risk", "alerts", p.ref?.dataset, p.ref?.well_id, p.depth, p.formation, p.radiusKm],
    queryFn: () => getRiskAlerts(p.ref!, { current_depth_m: p.depth, current_formation: p.formation, radius_km: p.radiusKm }),
    enabled: p.ready,
  });
}
