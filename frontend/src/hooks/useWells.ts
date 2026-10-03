import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listWells, lookupWell } from "@/api/wells";
import type { WellLocation, WellRef } from "@/api/types";
import { wellKey } from "@/lib/format";

export function useWells() {
  return useQuery({ queryKey: ["wells", "all"], queryFn: () => listWells(undefined, 500), staleTime: 30 * 60_000 });
}

export function useWellIndex() {
  const q = useWells();
  const index = useMemo(() => {
    const byKey = new Map<string, WellLocation>();
    const byId = new Map<string, WellLocation[]>();
    for (const w of q.data?.wells ?? []) {
      byKey.set(wellKey(w), w);
      byId.set(w.well_id, [...(byId.get(w.well_id) ?? []), w]);
    }
    return { byKey, byId };
  }, [q.data]);
  return { ...q, ...index };
}

export function useWellLookup(ref: WellRef | null) {
  return useQuery({
    queryKey: ["wells", "lookup", ref?.dataset, ref?.well_id],
    queryFn: () => lookupWell(ref!),
    enabled: !!ref,
  });
}
