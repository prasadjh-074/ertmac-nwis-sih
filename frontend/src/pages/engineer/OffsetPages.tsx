import { useState } from "react";
import type { WellRef } from "@/api/types";
import { useNearbyWells } from "@/hooks/useNearbyWells";
import { useSimilarWells } from "@/hooks/useSimilarWells";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtCoord, fmtKm, fmtScore, sameWell, wellKey } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Panel, ToolButton } from "@/components/nwis/Panel";
import { ThinBar } from "@/components/nwis/Meter";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/nwis/States";
import { WellDetailPanel } from "@/features/wells/WellDetailPanel";
import { useNavigate } from "react-router-dom";

const DS = [undefined, "VOLVE", "FORCE_2020"] as const;

function Layout({ table, selected, onClose }: { table: React.ReactNode; selected: WellRef | null; onClose: () => void }) {
  return (
    <div className="grid h-full min-h-[560px] grid-cols-1 gap-1.5 p-1.5 lg:grid-cols-[minmax(0,1fr)_340px]">
      {table}
      <div className="min-h-[420px]">
        {selected ? <WellDetailPanel key={wellKey(selected)} refs={[selected]} onClose={onClose} /> : (
          <div className="flex h-full items-center border border-dashed border-line bg-panel/40 hatch"><EmptyState title="No well selected" hint="Select a row to inspect distance, similarity, events and risk for that offset well." /></div>
        )}
      </div>
    </div>
  );
}

function DatasetFilter({ value, onChange, testid }: { value: string | undefined; onChange: (v: string | undefined) => void; testid: string }) {
  return (
    <div className="flex gap-1">
      {DS.map((d) => <ToolButton key={d ?? "all"} testid={`${testid}-${d ?? "all"}`} active={value === d} onClick={() => onChange(d)}>{d ?? "All datasets"}</ToolButton>)}
    </div>
  );
}

export function NearbyPage() {
  const ws = useWorkspace();
  const navigate = useNavigate();
  const [limit, setLimit] = useState(20);
  const [ds, setDs] = useState<string | undefined>();
  const [sel, setSel] = useState<WellRef | null>(null);
  const q = useNearbyWells(ws.currentWell, ws.radiusKm, limit, ds);
  const max = Math.max(...(q.data?.results.map((r) => r.distance_km) ?? [1]), 0.001);

  const table = (
    <Panel code="02" title="Nearby wells" meta={q.data ? `${q.data.count} within ${q.data.radius_km} km · Haversine` : undefined} testid="nearby-panel"
      actions={<>
        <DatasetFilter value={ds} onChange={setDs} testid="nearby-dataset" />
        <select data-testid="nearby-radius-select" value={ws.radiusKm} onChange={(e) => ws.setRadiusKm(Number(e.target.value))} className="h-7 border border-line bg-panel2 px-1 font-mono text-[10px] text-dim">
          {[10, 25, 50, 100, 200, 500].map((r) => <option key={r} value={r}>{r} km</option>)}
        </select>
        <select data-testid="nearby-limit-select" value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="h-7 border border-line bg-panel2 px-1 font-mono text-[10px] text-dim">
          {[10, 20, 50].map((r) => <option key={r} value={r}>top {r}</option>)}
        </select>
        <ToolButton testid="nearby-show-map-btn" disabled={!q.data?.count} onClick={() => { ws.setHighlight({ refs: q.data!.results, label: "Nearby set" }); navigate("/engineer/map"); }}>Map</ToolButton>
      </>}>
      {!ws.currentWell ? <EmptyState title="No current well" /> : q.isLoading ? <SkeletonLines rows={8} /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.count ? <EmptyState title="No wells in radius" hint="Increase the search radius." /> : (
        <table className="w-full text-left text-[12px]" data-testid="nearby-table">
          <thead className="sticky top-0 bg-panel font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
            <tr className="border-b border-line"><th className="px-3 py-1.5">#</th><th>Well</th><th>Dataset</th><th>Field</th><th>Discovery</th><th className="w-[22%]">Distance</th><th>Position</th></tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {q.data.results.map((r, i) => (
              <tr key={wellKey(r)} data-testid={`nearby-row-${i}`} onClick={() => setSel(r)} className={cn("cursor-pointer transition-colors hover:bg-panel2", sameWell(sel, r) && "bg-signal-deep/40")}>
                <td className="px-3 py-1.5 font-mono text-faint">{r.rank}</td>
                <td className="font-mono">{r.well_id}</td>
                <td className="font-mono text-[10px] text-dim">{r.dataset}</td>
                <td className="text-dim">{r.field_name ?? "—"}</td>
                <td className="text-dim">{r.discovery_name ?? "—"}</td>
                <td className="pr-4"><div className="flex items-center gap-2"><span className="w-16 font-mono tnum">{fmtKm(r.distance_km)}</span><ThinBar value={1 - r.distance_km / max} className="flex-1" /></div></td>
                <td className="pr-3 font-mono text-[10px] text-faint">{fmtCoord(r.latitude, r.longitude)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
  return <Layout table={table} selected={sel} onClose={() => setSel(null)} />;
}

export function SimilarPage() {
  const ws = useWorkspace();
  const navigate = useNavigate();
  const [topK, setTopK] = useState(10);
  const [ds, setDs] = useState<string | undefined>();
  const [sel, setSel] = useState<WellRef | null>(null);
  const q = useSimilarWells(ws.currentWell, topK, ds);
  const table = (
    <Panel code="03" title="Geologically similar wells" meta="cosine similarity · 30-dim well-log embeddings" testid="similar-panel"
      actions={<>
        <DatasetFilter value={ds} onChange={setDs} testid="similar-dataset" />
        <select data-testid="similar-topk-select" value={topK} onChange={(e) => setTopK(Number(e.target.value))} className="h-7 border border-line bg-panel2 px-1 font-mono text-[10px] text-dim">
          {[5, 10, 20, 50].map((r) => <option key={r} value={r}>top {r}</option>)}
        </select>
        <ToolButton testid="similar-show-map-btn" disabled={!q.data?.count} onClick={() => { ws.setHighlight({ refs: q.data!.results, label: "Similar set" }); navigate("/engineer/map"); }}>Map</ToolButton>
      </>}>
      {!ws.currentWell ? <EmptyState title="No current well" /> : q.isLoading ? <SkeletonLines rows={8} /> : q.isError ? <ErrorState error={q.error} context="Similarity search unavailable for this well (it may have no embedded log windows)." onRetry={() => q.refetch()} /> : !q.data?.count ? <EmptyState title="No similar wells returned" /> : (
        <>
          <table className="w-full text-left text-[12px]" data-testid="similar-table">
            <thead className="sticky top-0 bg-panel font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
              <tr className="border-b border-line"><th className="px-3 py-1.5">#</th><th>Well</th><th>Dataset</th><th className="w-[30%]">Similarity</th><th>Windows pooled</th><th>Pooling fraction</th></tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {q.data.results.map((r, i) => (
                <tr key={wellKey(r)} data-testid={`similar-row-${i}`} onClick={() => setSel(r)} className={cn("cursor-pointer transition-colors hover:bg-panel2", sameWell(sel, r) && "bg-signal-deep/40")}>
                  <td className="px-3 py-1.5 font-mono text-faint">{r.rank}</td>
                  <td className="font-mono">{r.well_id}</td>
                  <td className="font-mono text-[10px] text-dim">{r.dataset}</td>
                  <td className="pr-4"><div className="flex items-center gap-2"><span className="w-12 font-mono tnum text-similar">{fmtScore(r.similarity)}</span><ThinBar value={r.similarity} tone="similar" className="flex-1" /></div></td>
                  <td className="font-mono tnum text-dim">{r.windows_pooled} / {r.windows_total}</td>
                  <td className="font-mono tnum text-dim">{r.pooling_fraction.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-3 py-2 font-mono text-[10px] text-faint">Similarity compares well-log curve statistics. It indicates log-response resemblance, not proven geological equivalence.</p>
        </>
      )}
    </Panel>
  );
  return <Layout table={table} selected={sel} onClose={() => setSel(null)} />;
}
