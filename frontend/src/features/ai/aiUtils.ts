import type { QueryResponse, WellLocation, WellRef } from "@/api/types";
import { wellKey } from "@/lib/format";

// Collects only well IDs the backend returned; never infers new ones.
export function wellRefsFromResponse(r: QueryResponse, byId: Map<string, WellLocation[]>): { refs: WellRef[]; unresolved: string[] } {
  const raw: { well_id: string; dataset?: string }[] = [];
  const push = (id: unknown, ds?: unknown) => typeof id === "string" && id && raw.push({ well_id: id, dataset: typeof ds === "string" ? ds : undefined });
  for (const e of r.evidence) push(e.well_id, e.metadata?.dataset ?? (e as Record<string, unknown>).dataset);
  for (const ra of r.risk_assessments) for (const h of (ra.historical_events as Record<string, unknown>[] | undefined) ?? []) push(h.well_id, h.dataset);
  const sq = r.structured_query ?? {};
  push(sq.target_well_id, sq.target_dataset);
  push(sq.comparison_well_id, sq.comparison_dataset);

  const out = new Map<string, WellRef>();
  const unresolved = new Set<string>();
  for (const x of raw) {
    const matches = (byId.get(x.well_id) ?? []).filter((w) => !x.dataset || w.dataset === x.dataset);
    if (!matches.length) {
      if (x.dataset) out.set(wellKey({ dataset: x.dataset, well_id: x.well_id }), { dataset: x.dataset, well_id: x.well_id });
      else unresolved.add(x.well_id);
    }
    for (const m of matches) out.set(wellKey(m), { dataset: m.dataset, well_id: m.well_id });
  }
  return { refs: [...out.values()], unresolved: [...unresolved] };
}

export const SUGGESTED_QUESTIONS = [
  "What happened in nearby wells around my current depth?",
  "Which nearby wells had stuck pipe events?",
  "Show wells similar to my current well.",
  "What risks apply at my current depth?",
  "What historical drilling problems occurred in this formation?",
];

// The backend interpreter needs the well named explicitly; this only appends context the engineer already set.
export function withWellContext(q: string, well: WellRef | null, depth: number | null): string {
  if (!well || q.includes(well.well_id)) return q;
  const d = depth != null ? ` at ${Math.round(depth)} m` : "";
  return `${q} (current well ${well.well_id}, dataset ${well.dataset}${d})`;
}
