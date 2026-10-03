import { useMemo } from "react";
import type { CorrelatedEvent, DrillingEvent } from "@/api/types";
import { useCorrelatedEvents, useWellEvents } from "@/hooks/useEvents";
import { useAssessmentParams } from "@/hooks/useWellState";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtDepth, fmtKm, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { LevelTag, toneForLevel } from "@/components/nwis/Tags";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/nwis/States";

interface Row {
  event: DrillingEvent;
  correlation?: CorrelatedEvent;
  own: boolean;
}

export function useTimelineRows(eventType?: string) {
  const p = useAssessmentParams();
  const own = useWellEvents(p.ref, eventType);
  const corr = useCorrelatedEvents(eventType);
  const rows = useMemo<Row[]>(() => {
    const out: Row[] = (own.data?.events ?? []).map((e) => ({ event: e, own: true }));
    for (const c of corr.data?.events ?? []) {
      if (c.source_well_id === p.ref?.well_id && c.source_dataset === p.ref?.dataset) continue;
      out.push({ event: c.event, correlation: c, own: false });
    }
    return out.sort((a, b) => (a.event.depth_start_m ?? Infinity) - (b.event.depth_start_m ?? Infinity));
  }, [own.data, corr.data, p.ref]);
  return { rows, isLoading: own.isLoading || corr.isLoading, error: own.error ?? corr.error, refetch: () => { own.refetch(); corr.refetch(); }, depth: p.depth };
}

const dot = (sev: string) => ({ crit: "bg-crit", warn: "bg-warn", ok: "bg-ok", info: "bg-signal", neutral: "bg-dim" })[toneForLevel(sev)];

export function EventTimeline({ eventType, compact = false }: { eventType?: string; compact?: boolean }) {
  const { currentWell, openDrawer } = useWorkspace();
  const { rows, isLoading, error, refetch, depth } = useTimelineRows(eventType);
  if (!currentWell) return <EmptyState title="No current well" />;
  if (isLoading) return <SkeletonLines rows={5} label="Historical events" />;
  if (error) return <ErrorState error={error} context="Event history unavailable." onRetry={refetch} />;
  if (!rows.length) return <EmptyState title="No historical events" hint="No extracted events for this well or its correlated offsets." testid="events-empty" />;

  let depthMarkerShown = depth == null;
  return (
    <ol data-testid="event-timeline" className="relative py-2">
      <span className="absolute bottom-2 left-[86px] top-2 w-px bg-line" />
      {rows.map((r, i) => {
        const showMarker = !depthMarkerShown && r.event.depth_start_m != null && depth != null && r.event.depth_start_m > depth;
        if (showMarker) depthMarkerShown = true;
        return (
          <li key={i}>
            {showMarker && <DepthMarker depth={depth!} />}
            <button type="button" data-testid={`timeline-event-${i}`} onClick={() => openDrawer({ kind: "event", event: r.event, correlation: r.correlation })} className="group grid w-full grid-cols-[72px_28px_1fr] items-start px-3 py-1.5 text-left transition-colors hover:bg-panel2">
              <span className="pt-0.5 text-right font-mono text-[11px] tnum text-dim">{fmtDepth(r.event.depth_start_m)}</span>
              <span className="flex justify-center pt-1.5"><span className={cn("relative z-[1] size-2 rotate-45", dot(r.event.severity))} /></span>
              <span className="min-w-0">
                <span className="flex items-center gap-2">
                  <span className="truncate font-semicond text-[12px] font-semibold uppercase tracking-[0.06em] group-hover:text-signal">{humanize(r.event.event_type)}</span>
                  <LevelTag level={r.event.severity} />
                </span>
                <span className="mt-0.5 block truncate font-mono text-[10px] text-faint">
                  {r.own ? "this well" : `${r.event.well_id} · ${fmtKm(r.correlation?.distance_km)}`}
                  {r.event.formation ? ` · fm ${r.event.formation}` : ""}
                  {r.correlation?.depth_overlap ? " · depth overlap" : ""}
                  {r.correlation?.formation_match ? " · formation match" : ""}
                </span>
                {!compact && r.event.subtype && <span className="mt-0.5 block text-[11px] text-dim">{r.event.subtype}</span>}
              </span>
            </button>
          </li>
        );
      })}
      {!depthMarkerShown && depth != null && <DepthMarker depth={depth} />}
    </ol>
  );
}

function DepthMarker({ depth }: { depth: number }) {
  return (
    <div data-testid="timeline-depth-marker" className="flex items-center gap-2 px-3 py-1">
      <span className="w-[72px] text-right font-mono text-[11px] font-semibold tnum text-signal">{fmtDepth(depth)}</span>
      <span className="h-px flex-1 border-t border-dashed border-signal/60" />
      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-signal">assessment depth</span>
    </div>
  );
}
