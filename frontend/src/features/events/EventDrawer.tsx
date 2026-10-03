import type { CorrelatedEvent, DrillingEvent } from "@/api/types";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtDepth, fmtKm, fmtNum, humanize } from "@/lib/format";
import { Drawer } from "@/components/nwis/Drawer";
import { KV, SectionLabel } from "@/components/nwis/Panel";
import { LevelTag, Tag } from "@/components/nwis/Tags";
import { ThinBar } from "@/components/nwis/Meter";

export function EventDrawer({ event, correlation }: { event: DrillingEvent; correlation?: CorrelatedEvent }) {
  const { closeDrawer } = useWorkspace();
  const p = event.provenance;
  const rf = Object.entries(correlation?.relevance_factors ?? {});
  return (
    <Drawer
      open
      onClose={closeDrawer}
      testid="event-provenance-drawer"
      kicker="Event provenance"
      title={<div className="flex items-center gap-3"><h2 className="font-semicond text-[20px] font-semibold uppercase">{humanize(event.event_type)}</h2><LevelTag level={event.severity} className="h-6" /></div>}
      headerExtra={<div className="font-mono text-[11px] text-dim">{event.well_id ?? correlation?.source_well_id} · {event.dataset ?? correlation?.source_dataset}</div>}
    >
      <div className="space-y-6">
        <div className="grid grid-cols-3 gap-4">
          <KV label="Depth start" value={fmtDepth(event.depth_start_m)} />
          <KV label="Depth end" value={fmtDepth(event.depth_end_m)} />
          <KV label="Formation" value={event.formation ?? "—"} />
          <KV label="Subtype" value={event.subtype ?? "—"} />
        </div>

        <section>
          <SectionLabel index="01">Extraction</SectionLabel>
          {p ? (
            <div className="mt-2 grid grid-cols-2 gap-4" data-testid="event-provenance-fields">
              <KV label="Source type" value={p.source_type ?? "—"} />
              <KV label="Source table" value={p.source_table ?? "—"} />
              <KV label="Extraction method" value={p.extraction_method ?? "—"} />
              <div>
                <div className="label">Extraction confidence</div>
                <div className="mt-0.5 font-mono text-[13px] tnum">{fmtNum(p.extraction_confidence, 2)}</div>
                {p.extraction_confidence != null && <ThinBar value={p.extraction_confidence} className="mt-1" />}
              </div>
            </div>
          ) : <p className="mt-2 text-[12px] text-faint">No provenance returned for this event.</p>}
        </section>

        <section>
          <SectionLabel index="02">Original text snippet</SectionLabel>
          {p?.raw_text_snippet ? (
            <blockquote data-testid="event-raw-snippet" className="mt-2 border-l-2 border-faint bg-panel2 px-3 py-2.5 font-mono text-[12px] leading-relaxed text-ink">“{p.raw_text_snippet}”</blockquote>
          ) : <p className="mt-2 text-[12px] text-faint">No source snippet returned.</p>}
        </section>

        {correlation && (
          <section>
            <SectionLabel index="03">Correlation to current well</SectionLabel>
            <div className="mt-2 grid grid-cols-2 gap-4" data-testid="event-correlation-fields">
              <KV label="Distance" value={fmtKm(correlation.distance_km)} />
              <KV label="Depth difference" value={fmtDepth(correlation.depth_difference_m)} />
              <div><div className="label">Depth overlap</div><Tag tone={correlation.depth_overlap ? "warn" : "neutral"} className="mt-1">{correlation.depth_overlap ? "Overlap" : "No overlap"}</Tag></div>
              <div><div className="label">Formation match</div><Tag tone={correlation.formation_match ? "warn" : "neutral"} className="mt-1">{correlation.formation_match ? "Match" : "No match"}</Tag></div>
            </div>
            {rf.length > 0 && (
              <div className="mt-3 border border-line">
                <div className="label border-b border-line px-2.5 py-1.5">Relevance factors</div>
                {rf.map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b border-line-soft px-2.5 py-1 font-mono text-[12px] last:border-b-0">
                    <span className="text-dim">{humanize(k)}</span><span className="tnum">{typeof v === "number" ? fmtNum(v, 3) : String(v)}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </Drawer>
  );
}
