import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AlertOctagon, ChevronDown, CornerDownRight, MapPinned, ScanSearch } from "lucide-react";
import type { EvidenceItem } from "@/api/types";
import type { Investigation } from "@/hooks/useQueryAI";
import { useWellIndex } from "@/hooks/useWells";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtNum, humanize, riskLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import { SectionLabel, ToolButton } from "@/components/nwis/Panel";
import { LevelTag, Tag } from "@/components/nwis/Tags";
import { Meter } from "@/components/nwis/Meter";
import { wellRefsFromResponse } from "./aiUtils";

const toneFor = (v: string) => (v === "success" ? "bg-ok" : v.startsWith("skip") ? "bg-raised" : v === "partial" ? "bg-warn" : "bg-crit");
const textFor = (v: string) => (v === "success" ? "text-ok" : v.startsWith("skip") ? "text-faint" : v === "partial" ? "text-warn" : "text-crit");

function Pipeline({ status }: { status: Record<string, string> }) {
  const entries = Object.entries(status);
  if (!entries.length) return null;
  return (
    <div data-testid="ai-pipeline" className="flex flex-wrap gap-px border border-line bg-line">
      {entries.map(([k, v]) => (
        <div key={k} title={`${k}: ${v}`} className="min-w-[78px] flex-1 bg-panel px-1.5 py-1">
          <div className={cn("h-0.5 w-full", toneFor(v))} />
          <div className="mt-1 truncate font-mono text-[9px] uppercase text-faint">{humanize(k)}</div>
          <div className={cn("font-mono text-[9px]", textFor(v))}>{v}</div>
        </div>
      ))}
    </div>
  );
}

function EvidenceRow({ e, i }: { e: EvidenceItem; i: number }) {
  const [open, setOpen] = useState(false);
  const meta = Object.entries(e.metadata ?? {});
  return (
    <li className="border-b border-line-soft last:border-b-0">
      <button type="button" data-testid={`ai-evidence-${i}`} onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-panel2">
        <Tag className="max-w-[120px] truncate">{e.source_system ?? "source"}</Tag>
        <span className="truncate text-[12px] text-dim">{humanize(e.entity_type)}</span>
        {e.well_id && <span className="truncate font-mono text-[11px]">{e.well_id}</span>}
        {e.similarity != null && <span className="ml-auto font-mono text-[10px] tnum text-faint">sim {fmtNum(e.similarity, 3)}</span>}
        <ChevronDown className={cn("size-3 shrink-0 text-faint transition-transform", !e.similarity && "ml-auto", open && "rotate-180")} />
      </button>
      {open && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 bg-panel2 px-3 py-2 font-mono text-[10px]">
          {e.source_id && <div className="col-span-2 text-faint">source_id · <span className="text-dim">{e.source_id}</span></div>}
          {meta.length ? meta.map(([k, v]) => <div key={k} className="truncate text-faint">{k} · <span className="text-dim">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span></div>) : <div className="text-faint">No metadata.</div>}
        </div>
      )}
    </li>
  );
}

export function QueryResult({ inv, onFollowUp, onFallback }: { inv: Investigation; onFollowUp?: () => void; onFallback?: () => void }) {
  const r = inv.response;
  const ws = useWorkspace();
  const index = useWellIndex();
  const navigate = useNavigate();
  const location = useLocation();
  const [evOpen, setEvOpen] = useState(false);
  const { refs } = wellRefsFromResponse(r, index.byId);
  const interpretFailed = r.errors.some((e) => e.stage === "interpret");
  const sources = Object.entries(r.evidence.reduce<Record<string, number>>((m, e) => ({ ...m, [e.source_system ?? "unknown"]: (m[e.source_system ?? "unknown"] ?? 0) + 1 }), {}));

  const showOnMap = () => {
    ws.setHighlight({ refs, label: "AI answer" });
    if (!["/engineer", "/engineer/map", "/engineer/assistant"].includes(location.pathname)) navigate("/engineer/map");
  };

  return (
    <article data-testid="ai-result" className="rise space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <span className="label">Question</span>
          <Tag tone={inv.mode === "structured" ? "neutral" : "info"}>{inv.mode === "structured" ? "Deterministic" : "Natural language"}</Tag>
          <span className="ml-auto font-mono text-[9px] text-faint">{r.metadata.total_execution_ms != null ? `${fmtNum(r.metadata.total_execution_ms, 0)} ms` : ""}</span>
        </div>
        <p data-testid="ai-result-question" className="mt-1 text-[13px] text-dim">{inv.question}</p>
      </div>

      <div>
        <SectionLabel>Answer</SectionLabel>
        <p data-testid="ai-result-answer" className="mt-2 whitespace-pre-line text-[14px] leading-relaxed text-ink">{r.answer || "No answer returned."}</p>
      </div>

      {r.errors.length > 0 && (
        <div data-testid="ai-result-errors" className="border border-crit/30 bg-crit-deep/40 px-3 py-2.5">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.1em] text-crit"><AlertOctagon className="size-3.5" />{interpretFailed ? "AI interpretation unavailable" : "Pipeline reported errors"}</div>
          <ul className="mt-1.5 space-y-1">
            {r.errors.map((e, i) => <li key={i} className="font-mono text-[11px] leading-relaxed text-dim"><span className="text-faint">{e.stage ?? "stage"} · {e.error_type ?? "error"} —</span> {e.message}</li>)}
          </ul>
          {interpretFailed && <p className="mt-2 text-[12px] text-dim">Operational well, event and risk data remain available. You can run this as a deterministic structured query (no LLM).</p>}
          {interpretFailed && onFallback && <ToolButton testid="ai-fallback-btn" className="mt-2" onClick={onFallback}>Open deterministic query</ToolButton>}
          <div className="mt-2 font-mono text-[10px] text-faint">REQUEST ID {inv.meta.requestId}</div>
        </div>
      )}

      {r.confidence_score && (
        <div data-testid="ai-result-confidence">
          <SectionLabel>Confidence</SectionLabel>
          <div className="mt-2 flex items-center gap-3">
            <span className="font-mono text-[22px] tnum">{r.confidence_score.value.toFixed(2)}</span>
            <Tag>{r.confidence_score.label}</Tag>
            <Meter value={r.confidence_score.value} className="flex-1" segments={24} />
          </div>
          <p className="mt-1 font-mono text-[10px] text-faint">{r.confidence_score.note ?? "Heuristic indicator — not a probability."}</p>
          {!!r.confidence_score.basis?.length && <ul className="mt-1.5 space-y-0.5">{r.confidence_score.basis.map((b, i) => <li key={i} className="text-[12px] text-dim">· {b}</li>)}</ul>}
        </div>
      )}

      {r.metadata.node_status && <div><SectionLabel>Query pipeline</SectionLabel><div className="mt-2"><Pipeline status={r.metadata.node_status} /></div></div>}

      {r.rationale.length > 0 && (
        <div data-testid="ai-result-rationale">
          <SectionLabel>Why</SectionLabel>
          <ol className="mt-2 space-y-1">{r.rationale.map((x, i) => <li key={i} className="flex gap-2 text-[13px] leading-relaxed"><span className="font-mono text-[11px] text-signal">{String(i + 1).padStart(2, "0")}</span>{x}</li>)}</ol>
        </div>
      )}

      <div data-testid="ai-result-evidence">
        <SectionLabel>Supporting evidence · {r.evidence.length}</SectionLabel>
        {sources.length ? <div className="mt-2 flex flex-wrap gap-1.5">{sources.map(([s, n]) => <Tag key={s} tone="info">{s} · {n}</Tag>)}</div> : <p className="mt-2 text-[12px] text-faint">No evidence items returned.</p>}
        {evOpen && r.evidence.length > 0 && <ul className="mt-2 border border-line">{r.evidence.slice(0, 40).map((e, i) => <EvidenceRow key={i} e={e} i={i} />)}</ul>}
      </div>

      {(r.risk_assessments.length > 0 || r.alerts.length > 0) && (
        <div>
          <SectionLabel>Relevant risks & alerts</SectionLabel>
          <ul className="mt-2 space-y-1">
            {r.risk_assessments.map((a, i) => <li key={`r${i}`} className="flex items-center gap-2 text-[12px]"><span className="w-32 text-dim">{riskLabel(String(a.risk_type))}</span><span className="font-mono tnum">{fmtNum(a.score, 3)}</span><LevelTag level={String(a.level ?? "unknown")} /></li>)}
            {r.alerts.map((a, i) => <li key={`a${i}`} className="flex items-center gap-2 text-[12px]"><LevelTag level={String(a.severity ?? "info")} /><span>{String(a.title ?? a.alert_type)}</span></li>)}
          </ul>
        </div>
      )}

      {r.provenance.length > 0 && (
        <div data-testid="ai-result-provenance">
          <SectionLabel>Provenance</SectionLabel>
          <ul className="mt-2 space-y-0.5">{r.provenance.map((p, i) => <li key={i} className="font-mono text-[11px] text-dim">{p}</li>)}</ul>
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 border-t border-line pt-3">
        <ToolButton testid="ai-show-on-map-btn" disabled={!refs.length} onClick={showOnMap}><MapPinned className="size-3.5" />Show on map{refs.length ? ` · ${refs.length}` : ""}</ToolButton>
        <ToolButton testid="ai-view-evidence-btn" disabled={!r.evidence.length} active={evOpen} onClick={() => setEvOpen(!evOpen)}><ScanSearch className="size-3.5" />View evidence</ToolButton>
        {onFollowUp && <ToolButton testid="ai-follow-up-btn" onClick={onFollowUp}><CornerDownRight className="size-3.5" />Ask follow-up</ToolButton>}
      </div>
      <div className="font-mono text-[9px] text-faint">request {inv.meta.requestId} · round-trip {fmtNum(inv.meta.roundTripMs, 0)} ms</div>
    </article>
  );
}
