import { useQuery } from "@tanstack/react-query";
import { getCorrelatedEvents, getEventsByFormation, getWellEvents } from "@/api/events";
import type { WellRef } from "@/api/types";
import { useAssessmentParams } from "./useWellState";

export function useWellEvents(ref: WellRef | null, eventType?: string) {
  return useQuery({
    queryKey: ["events", "well", ref?.dataset, ref?.well_id, eventType ?? null],
    queryFn: () => getWellEvents(ref!, eventType),
    enabled: !!ref,
  });
}

export function useCorrelatedEvents(eventType?: string, limit = 50) {
  const p = useAssessmentParams();
  return useQuery({
    queryKey: ["events", "correlated", p.ref?.dataset, p.ref?.well_id, p.depth, p.formation, p.radiusKm, limit, eventType ?? null],
    queryFn: () =>
      getCorrelatedEvents(p.ref!, {
        current_depth_m: p.depth,
        current_formation: p.formation,
        radius_km: p.radiusKm,
        limit,
        event_type: eventType,
      }),
    enabled: p.ready,
  });
}

export function useFormationEvents(formation: string) {
  return useQuery({
    queryKey: ["events", "formation", formation],
    queryFn: () => getEventsByFormation(formation),
    enabled: formation.trim().length > 0,
  });
}
