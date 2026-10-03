import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Bot, Crosshair, GitCompareArrows, ShieldAlert, X } from "lucide-react";
import type { WellRef } from "@/api/types";
import { getSimilarWells } from "@/api/wells";
import { useWellIndex } from "@/hooks/useWells";
import { useNearbyWells } from "@/hooks/useNearbyWells";
import { useSimilarWells } from "@/hooks/useSimilarWells";
import { useWellContext } from "@/hooks/useWellContext";
import { useWellEvents } from "@/hooks/useEvents";
import { useWellRiskSnapshot } from "@/hooks/useRisk";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtCoord, fmtDepth, fmtKm, fmtScore, humanize, riskLabel, sameWell, wellKey } from "@/lib/format";
import { cn } from "@/lib/utils";
import { KV } from "@/components/nwis/Panel";
import { LevelTag, Tag } from "@/components/nwis/Tags";
import { ErrorState, SkeletonLines } from "@/components/nwis/States";

function Action({ icon: Icon, children, onClick, testid, disabled }: { icon: typeof X; children: React.ReactNode; onClick: () => void; testid: string; disabled?: boolean }) {
  return (
    <button type="button" data-testid={testid} disabled={disabled} onClick={onClick} className="flex h-8 items-center gap-2 border border-line bg-panel2 px-2.5 text-left font-mono text-[10px] uppercase tracking-[0.08em] text-dim transition-colors hover:border-signal/50 hover:text-ink disabled:opacity-40">
      <Icon className="size-3.5 shrink-0" strokeWidth={1.5} /> {children}
    </button>
  );
}

function OffsetEvents({ wref }: { wref: WellRef }) {
  const { openDrawer } = useWorkspace();
  const ev = useWellEvents(wref);
  if (ev.isLoading) return <SkeletonLines rows={2} className="px-0" />;
  if (ev.isError) return <ErrorState error={ev.error} />;
  if (!ev.data?.count) return <p className="text-[12px] text-faint">No extracted drilling events for this well.</p>;
  return (
    <ul className="divide-y divide-line-soft border border-line">
      {ev.data.events.slice(0, 6).map((e, i) => (
        <li key={i}>
          <button type="button" data-testid={`detail-event-${i}`} onClick={() => openDrawer({ kind: "event", event: e })} className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-panel2">
            <span className="w-16 font-mono text-[11px] tnum text-dim">{fmtDepth(e.depth_start_m)}</span>
            <span className="flex-1 truncate text-[12px] uppercase">{humanize(e.event_type)}</span>
            <LevelTag level={e.severity} />
          </button>
        </li>
      ))}
    </ul>
  );
}

function OffsetRisk({ wref }: { wref: WellRef }) {
  const r = useWellRiskSnapshot(wref);
  if (r.isLoading) return <SkeletonLines rows={3} className="px-0" label="Risk assessment" />;
  if (r.isError) return <ErrorState error={r.error} />;
  const items = [...(r.data?.assessments ?? [])].sort((a, b) => b.score - a.score);
  return (
    <div className="space-y-1">
      {items.map((a) => (
        <div key={a.risk_type} className="flex items-center gap-2 text-[12px]">
          <span className="w-28 truncate text-dim">{riskLabel(a.risk_type)}</span>
          <span className="w-12 font-mono tnum">{fmtScore(a.score)}</span>
          <LevelTag level={a.level} />
        </div>
      ))}
      <p className="pt-1 font-mono text-[10px] text-faint">Score without depth context · heuristic, not a probability</p>
    </div>
  );
}

export function WellDetailPanel({ refs, onClose }: { refs: WellRef[]; onClose: () => void }) {
  const [idx, setIdx] = useState(0);
  const [tab, setTab] = useState<"events" | "risk" | null>(null);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const ws = useWorkspace();
  const ref = refs[Math.min(idx, refs.length - 1)];
  const index = useWellIndex();
  const nearby = useNearbyWells(ws.currentWell, ws.radiusKm, 20);
  const similar = useSimilarWells(ws.currentWell, 10);
  const ctx = useWellContext(ref, ws.radiusKm);
  const loc = index.byKey.get(wellKey(ref));
  const near = nearby.data?.results.find((n) => sameWell(n, ref));
  const sim = similar.data?.results.find((s) => sameWell(s, ref));
  const isCurrent = sameWell(ref, ws.currentWell);

  const showSimilar = async () => {
    const data = await qc.fetchQuery({ queryKey: ["wells", "similar", ref.dataset, ref.well_id, 10, null], queryFn: () => getSimilarWells(ref, 10) });
    ws.setHighlight({ refs: data.results.map((s) => ({ dataset: s.dataset, well_id: s.well_id })), label: `Similar to ${ref.well_id}` });
  };

  return (
    <aside data-testid="well-detail-panel" className="rise flex h-full flex-col border border-line bg-panel">
      <header className="border-b border-line px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="label">Well</span>
          {isCurrent && <Tag tone="info">Current</Tag>}
          {near && !isCurrent && <Tag tone="info">Nearby #{near.rank}</Tag>}
          {sim && <Tag className="text-similar border-similar/40">Similar #{sim.rank}</Tag>}
          <button type="button" onClick={onClose} data-testid="well-detail-close-btn" className="ml-auto text-dim hover:text-ink"><X className="size-4" /></button>
        </div>
        <div className="mt-1 font-mono text-[18px] font-medium text-ink" data-testid="well-detail-id">{ref.well_id}</div>
        {refs.length > 1 && (
          <div className="mt-2 flex flex-wrap gap-1" data-testid="well-detail-colocated">
            <span className="label w-full">{refs.length} wells at this location</span>
            {refs.map((r, i) => (
              <button key={wellKey(r)} type="button" data-testid={`colocated-${i}`} onClick={() => { setIdx(i); setTab(null); }} className={cn("border px-1.5 py-0.5 font-mono text-[10px]", i === idx ? "border-signal/60 text-signal" : "border-line text-dim hover:text-ink")}>
                {r.well_id}
              </button>
            ))}
          </div>
        )}
      </header>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-3">
        <div className="grid grid-cols-2 gap-x-3 gap-y-3">
          <KV label="Dataset" value={ref.dataset} />
          <KV label="Field" value={loc?.field_name ?? ctx.data?.field_name ?? "—"} mono={false} />
          <KV label="Operator" value={ctx.isLoading ? "…" : ctx.data?.operator ?? "—"} mono={false} />
          <KV label="Status" value={ctx.isLoading ? "…" : ctx.data?.status ?? "—"} />
          <KV label="Historical TD" value={ctx.isLoading ? "…" : fmtDepth(ctx.data?.total_depth_m)} />
          <KV label="SODIR wellbore" value={loc?.sodir_wellbore_name ?? "—"} />
          <KV label="Distance to current" value={isCurrent ? "0 · reference" : near ? fmtKm(near.distance_km) : "Outside nearby set"} testid="well-detail-distance" />
          <KV label="Similarity" value={sim ? fmtScore(sim.similarity) : isCurrent ? "reference" : "Not in top-10"} testid="well-detail-similarity" />
        </div>
        <KV label="Coordinates" value={fmtCoord(loc?.latitude, loc?.longitude)} />
        {loc?.discovery_name && <KV label="Discovery" value={loc.discovery_name} mono={false} />}

        <div className="grid grid-cols-2 gap-1.5">
          <Action icon={Crosshair} testid="well-detail-set-current-btn" disabled={isCurrent} onClick={() => ws.setCurrentWell(ref)}>{isCurrent ? "Is current well" : "Set as current"}</Action>
          <Action icon={ArrowUpRight} testid="well-detail-view-events-btn" onClick={() => setTab(tab === "events" ? null : "events")}>View events</Action>
          <Action icon={ShieldAlert} testid="well-detail-view-risk-btn" onClick={() => setTab(tab === "risk" ? null : "risk")}>View risk</Action>
          <Action icon={GitCompareArrows} testid="well-detail-show-similar-btn" onClick={showSimilar}>Show similar</Action>
          <Action icon={Bot} testid="well-detail-ask-ai-btn" onClick={() => { ws.setAiDraft(`What drilling events occurred in well ${ref.well_id}?`); navigate("/engineer/assistant"); }}>Ask AI</Action>
        </div>

        {tab === "events" && <div className="space-y-2"><div className="label">Historical drilling events</div><OffsetEvents wref={ref} /></div>}
        {tab === "risk" && <div className="space-y-2"><div className="label">Risk snapshot</div><OffsetRisk wref={ref} /></div>}
      </div>
    </aside>
  );
}
