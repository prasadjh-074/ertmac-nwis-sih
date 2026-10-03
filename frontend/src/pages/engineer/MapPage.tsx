import { useMemo, useState } from "react";
import { MapPinOff } from "lucide-react";
import { useWellIndex } from "@/hooks/useWells";
import { useNearbyWells } from "@/hooks/useNearbyWells";
import { useSimilarWells } from "@/hooks/useSimilarWells";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtKm, fmtScore, sameWell, wellKey } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Panel } from "@/components/nwis/Panel";
import { ErrorState, SkeletonLines } from "@/components/nwis/States";
import { WorkspaceMap } from "@/features/map/WorkspaceMap";

type Filter = "all" | "nearby" | "similar" | "VOLVE" | "FORCE_2020";

export default function MapPage() {
  const ws = useWorkspace();
  const index = useWellIndex();
  const nearby = useNearbyWells(ws.currentWell, ws.radiusKm, 20);
  const similar = useSimilarWells(ws.currentWell, 10);
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");

  const rows = useMemo(() => {
    const nb = new Map((nearby.data?.results ?? []).map((n) => [wellKey(n), n]));
    const sm = new Map((similar.data?.results ?? []).map((s) => [wellKey(s), s]));
    return (index.data?.wells ?? [])
      .map((w) => ({ w, n: nb.get(wellKey(w)), s: sm.get(wellKey(w)) }))
      .filter(({ w, n, s }) =>
        (filter === "all" || (filter === "nearby" && n) || (filter === "similar" && s) || w.dataset === filter) &&
        (!q || w.well_id.toLowerCase().includes(q.toLowerCase()) || (w.field_name ?? "").toLowerCase().includes(q.toLowerCase())))
      .sort((a, b) => (a.n?.distance_km ?? 1e9) - (b.n?.distance_km ?? 1e9) || (b.s?.similarity ?? 0) - (a.s?.similarity ?? 0));
  }, [index.data, nearby.data, similar.data, filter, q]);

  return (
    <div data-testid="map-page" className="grid h-full min-h-[600px] grid-cols-1 gap-1.5 p-1.5 lg:grid-cols-[340px_minmax(0,1fr)]">
      <Panel code="01" title="Well register" meta={`${rows.length} / ${index.data?.count ?? "…"}`} testid="map-register-panel" className="max-h-[50vh] lg:max-h-none">
        <div className="sticky top-0 z-[1] space-y-1.5 border-b border-line bg-panel p-2">
          <input data-testid="map-register-filter-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by well or field" className="h-7 w-full border border-line bg-panel2 px-2 font-mono text-[11px] outline-none focus:border-signal/60" />
          <div className="flex flex-wrap gap-1">
            {(["all", "nearby", "similar", "VOLVE", "FORCE_2020"] as Filter[]).map((f) => (
              <button key={f} type="button" data-testid={`map-register-filter-${f}`} onClick={() => setFilter(f)} className={cn("h-6 border px-1.5 font-mono text-[10px] uppercase", filter === f ? "border-signal/60 text-signal" : "border-line text-dim hover:text-ink")}>{f}</button>
            ))}
          </div>
        </div>
        {index.isLoading ? <SkeletonLines rows={10} /> : index.isError ? <ErrorState error={index.error} onRetry={() => index.refetch()} /> : (
          <table className="w-full text-left text-[12px]">
            <thead className="sticky top-[73px] bg-panel font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
              <tr className="border-b border-line"><th className="px-2 py-1">Well</th><th className="px-1">Dist.</th><th className="px-1">Sim.</th><th /></tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {rows.map(({ w, n, s }, i) => {
                const ref = { dataset: w.dataset, well_id: w.well_id };
                const selected = ws.selection?.some((x) => sameWell(x, ref));
                return (
                  <tr key={wellKey(w)} data-testid={`map-register-row-${i}`} onClick={() => w.has_coordinates && ws.selectWells([ref])} className={cn("cursor-pointer transition-colors hover:bg-panel2", selected && "bg-signal-deep/40", sameWell(ref, ws.currentWell) && "text-signal")}>
                    <td className="px-2 py-1.5"><div className="font-mono text-[11px]">{w.well_id}</div><div className="font-mono text-[9px] text-faint">{w.dataset} · {w.field_name ?? "no field"}</div></td>
                    <td className="px-1 font-mono text-[11px] tnum text-dim">{n ? fmtKm(n.distance_km) : ""}</td>
                    <td className="px-1 font-mono text-[11px] tnum text-similar">{s ? fmtScore(s.similarity) : ""}</td>
                    <td className="pr-2">{!w.has_coordinates && <MapPinOff className="size-3 text-faint" aria-label="No coordinates" />}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Panel>
      <WorkspaceMap className="min-h-[520px]" />
    </div>
  );
}
