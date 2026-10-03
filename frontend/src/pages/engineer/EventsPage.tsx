import { useMemo, useState } from "react";
import { ArrowRight } from "lucide-react";
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { useCorrelatedEvents, useFormationEvents } from "@/hooks/useEvents";
import { useAssessmentParams } from "@/hooks/useWellState";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtDepth, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Panel, ToolButton } from "@/components/nwis/Panel";
import { LevelTag } from "@/components/nwis/Tags";
import { EmptyState, ErrorState, SkeletonBlock, SkeletonLines } from "@/components/nwis/States";
import { EventTimeline } from "@/features/events/EventTimeline";

const TYPES = ["mud_loss", "stuck_pipe", "kick", "overpressure", "torque_spike", "cementing_issue", "casing_issue", "fishing", "npt", "other"];
const COLORS: Record<string, string> = { mud_loss: "#2ec5d8", stuck_pipe: "#f0554c", kick: "#f0a63a", overpressure: "#f0a63a", torque_spike: "#d9a441", cementing_issue: "#2fb47f", casing_issue: "#94a1b4", fishing: "#94a1b4", npt: "#94a1b4", other: "#5b687b" };

function CorrelationFlow() {
  const p = useAssessmentParams();
  const corr = useCorrelatedEvents();
  const ev = corr.data?.events ?? [];
  const steps = [
    { label: "Current well", value: p.ref?.well_id ?? "—" },
    { label: "Offset wells", value: corr.data ? String(new Set(ev.map((e) => e.source_well_id)).size) : "…" },
    { label: "Depth overlap", value: corr.data ? String(ev.filter((e) => e.depth_overlap).length) : "…" },
    { label: "Formation match", value: corr.data ? String(ev.filter((e) => e.formation_match).length) : "…" },
    { label: "Correlated events", value: corr.data ? String(corr.data.count) : "…" },
  ];
  return (
    <div data-testid="correlation-flow" className="flex flex-wrap items-stretch border border-line bg-panel">
      {steps.map((s, i) => (
        <div key={s.label} className="flex items-center">
          <div className="px-4 py-2.5">
            <div className="label">{s.label}</div>
            <div className={cn("mt-0.5 font-mono text-[18px] tnum", i === 0 ? "text-signal" : "text-ink")}>{s.value}</div>
          </div>
          {i < steps.length - 1 && <ArrowRight className="size-4 text-faint" />}
        </div>
      ))}
      <div className="ml-auto self-center px-4 font-mono text-[10px] text-faint">radius {p.radiusKm} km · depth {fmtDepth(p.depth)} · fm {p.formation ?? "—"}</div>
    </div>
  );
}

function DepthChart({ eventType }: { eventType?: string }) {
  const p = useAssessmentParams();
  const corr = useCorrelatedEvents(eventType);
  const data = useMemo(() => (corr.data?.events ?? [])
    .filter((c) => c.event.depth_start_m != null && c.distance_km != null)
    .map((c) => ({ x: c.distance_km!, y: c.event.depth_start_m!, type: c.event.event_type, well: c.source_well_id })), [corr.data]);
  if (corr.isLoading) return <SkeletonBlock className="m-3 h-[260px]" />;
  if (corr.isError) return <ErrorState error={corr.error} />;
  if (!data.length) return <EmptyState title="No events with depth and distance" />;
  const types = [...new Set(data.map((d) => d.type))];
  return (
    <div className="h-full min-h-[280px] p-2" data-testid="event-depth-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 20, bottom: 24, left: 8 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="2 4" />
          <XAxis type="number" dataKey="x" name="Distance" unit=" km" stroke="#5b687b" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} label={{ value: "distance from current well (km)", position: "insideBottom", offset: -12, fill: "#5b687b", fontSize: 10 }} />
          <YAxis type="number" dataKey="y" name="Depth" unit=" m" reversed stroke="#5b687b" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} width={64} />
          <ZAxis range={[60, 60]} />
          {p.depth != null && <ReferenceLine y={p.depth} stroke="#2ec5d8" strokeDasharray="4 3" label={{ value: `assessment ${Math.round(p.depth)} m`, fill: "#2ec5d8", fontSize: 10, position: "insideTopRight" }} />}
          <Tooltip cursor={{ stroke: "#1e293b" }} contentStyle={{ background: "#0d1219", border: "1px solid #1e293b", fontFamily: "IBM Plex Mono", fontSize: 11 }} formatter={(v: number, n: string) => [v, n]} />
          {types.map((t) => <Scatter key={t} name={humanize(t)} data={data.filter((d) => d.type === t)} fill={COLORS[t] ?? "#94a1b4"} shape="diamond" />)}
        </ScatterChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-3 px-2 font-mono text-[10px] text-dim">
        {types.map((t) => <span key={t} className="flex items-center gap-1.5"><span className="size-2 rotate-45" style={{ background: COLORS[t] ?? "#94a1b4" }} />{humanize(t)}</span>)}
      </div>
    </div>
  );
}

function FormationLookup() {
  const p = useAssessmentParams();
  const { openDrawer } = useWorkspace();
  const [input, setInput] = useState(p.formation ?? "");
  const [term, setTerm] = useState("");
  const q = useFormationEvents(term);
  return (
    <Panel code="04.3" title="Formation history" meta="GET /events/formation" testid="formation-panel">
      <form className="flex gap-1.5 border-b border-line p-2" onSubmit={(e) => { e.preventDefault(); setTerm(input.trim()); }}>
        <input data-testid="formation-search-input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Formation name, e.g. Draupne" className="h-7 flex-1 border border-line bg-panel2 px-2 font-mono text-[11px] outline-none focus:border-signal/60" />
        <ToolButton testid="formation-search-btn" onClick={() => setTerm(input.trim())}>Search</ToolButton>
      </form>
      {!term ? <EmptyState title="Enter a formation" hint="Lists all extracted events recorded in that formation, across wells." /> : q.isLoading ? <SkeletonLines rows={3} /> : q.isError ? <ErrorState error={q.error} /> : !q.data?.count ? <EmptyState title="No events in this formation" /> : (
        <ul className="divide-y divide-line-soft">
          {q.data.events.map((e, i) => (
            <li key={i}><button type="button" data-testid={`formation-event-${i}`} onClick={() => openDrawer({ kind: "event", event: e })} className="flex w-full items-center gap-3 px-3 py-1.5 text-left hover:bg-panel2">
              <span className="w-20 font-mono text-[11px]">{e.well_id}</span><span className="w-16 font-mono text-[11px] text-dim">{fmtDepth(e.depth_start_m)}</span><span className="flex-1 uppercase">{humanize(e.event_type)}</span><LevelTag level={e.severity} />
            </button></li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export default function EventsPage() {
  const [type, setType] = useState<string | undefined>();
  return (
    <div data-testid="events-page" className="flex min-h-full flex-col gap-1.5 p-1.5 xl:h-full">
      <CorrelationFlow />
      <div className="flex flex-wrap gap-1">
        <ToolButton testid="event-type-all" active={!type} onClick={() => setType(undefined)}>All types</ToolButton>
        {TYPES.map((t) => <ToolButton key={t} testid={`event-type-${t}`} active={type === t} onClick={() => setType(t)}>{humanize(t)}</ToolButton>)}
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-1.5 lg:grid-cols-[400px_minmax(0,1fr)]">
        <Panel code="04.1" title="Drilling history" meta="sorted by depth" testid="events-timeline-panel" className="min-h-[420px]"><EventTimeline eventType={type} /></Panel>
        <div className="grid min-h-0 grid-rows-[minmax(300px,1.3fr)_minmax(220px,1fr)] gap-1.5">
          <Panel code="04.2" title="Offset events · depth vs distance" meta="where do correlated events sit relative to the assessment depth?" testid="events-chart-panel"><DepthChart eventType={type} /></Panel>
          <FormationLookup />
        </div>
      </div>
    </div>
  );
}
