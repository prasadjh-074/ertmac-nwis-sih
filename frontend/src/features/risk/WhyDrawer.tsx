import { useLocation, useNavigate } from "react-router-dom";
import { MapPinned } from "lucide-react";
import type { Alert, HistoricalEventRecord, RiskAssessment, RuleResult, WellRef } from "@/api/types";
import { useRiskAssessment } from "@/hooks/useRisk";
import { useRiskAlerts } from "@/hooks/useAlerts";
import { useCorrelatedEvents } from "@/hooks/useEvents";
import { useAssessmentParams } from "@/hooks/useWellState";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtDepth, fmtKm, fmtNum, fmtScore, humanize, RISK_LABELS, riskLabel, riskTypeForRule } from "@/lib/format";
import { Drawer } from "@/components/nwis/Drawer";
import { PrimaryButton, SectionLabel } from "@/components/nwis/Panel";
import { LevelTag, Tag } from "@/components/nwis/Tags";
import { Meter } from "@/components/nwis/Meter";
import { SkeletonLines } from "@/components/nwis/States";
import { meterTone } from "./RiskMatrix";

const MAP_ROUTES = ["/engineer", "/engineer/map", "/engineer/assistant"];

function resolve(alert: Alert | undefined, riskType: string | undefined, assessments: RiskAssessment[], rules: RuleResult[], alerts: Alert[]) {
  const key = riskType ?? alert?.alert_type ?? "";
  const isRisk = key in RISK_LABELS;
  const rule = isRisk ? undefined : rules.find((r) => r.rule_type === key);
  const riskKey = isRisk ? key : riskTypeForRule(key);
  const assessment = assessments.find((a) => a.risk_type === riskKey);
  const theAlert = alert ?? alerts.find((a) => a.alert_type === key);
  return { key, isRisk, rule, assessment, alert: theAlert };
}

function Value({ v }: { v: unknown }) {
  if (typeof v === "number") return <>{Number.isInteger(v) ? v : fmtNum(v, 3)}</>;
  if (typeof v === "boolean") return <>{v ? "yes" : "no"}</>;
  if (v == null) return <>—</>;
  if (typeof v === "object") return <>{JSON.stringify(v)}</>;
  return <>{String(v)}</>;
}

function EventsTable({ rows, onRow }: { rows: HistoricalEventRecord[]; onRow: (r: HistoricalEventRecord) => void }) {
  if (!rows.length) return <p className="text-[12px] text-faint">No historical events contributed to this assessment.</p>;
  return (
    <div className="overflow-x-auto border border-line">
      <table className="w-full text-left text-[12px]" data-testid="why-events-table">
        <thead className="bg-panel2 font-mono text-[10px] uppercase tracking-[0.08em] text-faint">
          <tr><th className="px-2 py-1.5">Well</th><th className="px-2">Depth</th><th className="px-2">Event</th><th className="px-2">Sev.</th><th className="px-2">Dist.</th><th className="px-2">Depth ovl.</th><th className="px-2">Fm. match</th></tr>
        </thead>
        <tbody className="divide-y divide-line-soft">
          {rows.map((r, i) => (
            <tr key={i} data-testid={`why-event-row-${i}`} onClick={() => onRow(r)} className="cursor-pointer transition-colors hover:bg-panel2">
              <td className="px-2 py-1.5 font-mono">{String(r.well_id ?? "—")}<div className="text-[9px] text-faint">{String(r.dataset ?? "")}</div></td>
              <td className="px-2 font-mono tnum">{fmtDepth((r.depth_m ?? r.depth_start_m) as number | null)}</td>
              <td className="px-2 uppercase">{humanize(r.event_type as string)}</td>
              <td className="px-2">{r.severity ? <LevelTag level={String(r.severity)} /> : "—"}</td>
              <td className="px-2 font-mono tnum">{fmtKm(r.distance_km as number | null)}</td>
              <td className="px-2 font-mono">{r.depth_overlap == null ? "—" : r.depth_overlap ? "yes" : "no"}</td>
              <td className="px-2 font-mono">{r.formation_match == null ? "—" : r.formation_match ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function WhyDrawer({ alert, riskType }: { alert?: Alert; riskType?: string }) {
  const ws = useWorkspace();
  const navigate = useNavigate();
  const location = useLocation();
  const params = useAssessmentParams();
  const risk = useRiskAssessment();
  const alerts = useRiskAlerts();
  const correlated = useCorrelatedEvents();
  const r = resolve(alert, riskType, risk.data?.assessments ?? [], risk.data?.rules ?? [], alerts.data?.alerts ?? []);
  const level = r.alert?.severity ?? r.assessment?.level ?? r.rule?.severity ?? "unknown";
  const rows = r.rule?.contributing_events?.length ? r.rule.contributing_events : r.assessment?.historical_events ?? [];
  const evidence = [...new Set([...(r.alert?.evidence ?? []), ...(r.rule?.evidence ?? []), ...(r.assessment?.evidence ?? [])])];
  const features = Object.entries({ ...(r.assessment?.contributing_features ?? {}), ...(r.rule?.details ?? {}) }).filter(([k]) => k !== "evidence");
  const limitations = r.assessment?.limitations ?? [];
  const title = r.isRisk ? `${riskLabel(r.key)} risk` : r.alert?.title ?? humanize(r.key).toUpperCase();

  const relatedRefs: WellRef[] = [...new Map(rows.filter((e) => e.well_id).map((e) => [`${e.dataset}::${e.well_id}`, { dataset: String(e.dataset ?? ""), well_id: String(e.well_id) }])).values()];

  const openEvent = (row: HistoricalEventRecord) => {
    const depth = row.depth_m ?? row.depth_start_m;
    const match = correlated.data?.events.find((c) => c.source_well_id === row.well_id && c.event.event_type === row.event_type && (depth == null || c.event.depth_start_m === depth));
    if (match) ws.openDrawer({ kind: "event", event: match.event, correlation: match });
  };

  const showOnMap = () => {
    ws.setHighlight({ refs: relatedRefs, label: `${riskLabel(r.isRisk ? r.key : riskTypeForRule(r.key) ?? r.key)} evidence` });
    ws.closeDrawer();
    if (!MAP_ROUTES.includes(location.pathname)) navigate("/engineer/map");
  };

  const loading = risk.isLoading || alerts.isLoading;

  return (
    <Drawer
      open
      onClose={ws.closeDrawer}
      testid="why-alert-drawer"
      kicker={alert ? "Why this alert?" : "Why this assessment?"}
      width="w-[min(720px,100vw)]"
      title={<div className="flex flex-wrap items-center gap-3"><h2 className="font-semicond text-[20px] font-semibold uppercase tracking-[0.04em]">{title}</h2><LevelTag level={level} className="h-6 text-[11px]" /></div>}
      headerExtra={<div className="font-mono text-[10px] text-faint">{params.ref?.well_id} · {params.ref?.dataset} · depth {fmtDepth(params.depth)} · formation {params.formation ?? "not resolved"} · radius {params.radiusKm} km</div>}
      footer={
        <div className="flex items-center gap-3">
          <PrimaryButton testid="why-show-on-map-btn" onClick={showOnMap} disabled={!relatedRefs.length}><MapPinned className="size-3.5" /> Show related wells on map</PrimaryButton>
          <span className="font-mono text-[10px] text-faint">{relatedRefs.length} related well(s) · decision support only</span>
        </div>
      }
    >
      {loading ? <SkeletonLines rows={8} /> : (
        <div className="space-y-6">
          <section>
            <SectionLabel index="01">Why was this raised?</SectionLabel>
            <p data-testid="why-explanation" className="mt-2 text-[13px] leading-relaxed text-ink">{r.alert?.explanation ?? r.assessment?.evidence.join(" ") ?? "—"}</p>
            {r.assessment && (
              <div className="mt-3 grid grid-cols-3 gap-4 border border-line bg-panel2 px-3 py-2.5">
                <div><div className="label">Risk score</div><div className="font-mono text-[18px] tnum">{fmtScore(r.assessment.score)}</div><Meter value={r.assessment.score} tone={meterTone(r.assessment.level)} className="mt-1" /></div>
                <div><div className="label">Confidence</div><div className="font-mono text-[18px] tnum">{r.assessment.confidence.toFixed(2)}</div><Meter value={r.assessment.confidence} tone="signal" className="mt-1" /></div>
                <div><div className="label">Assessment</div><div className="mt-1 text-[12px] text-dim">Rule-based evidence score — not a calibrated probability</div></div>
              </div>
            )}
          </section>
          <section>
            <SectionLabel index="02">Contributing evidence</SectionLabel>
            <ul className="mt-2 space-y-1.5" data-testid="why-evidence-list">
              {evidence.length ? evidence.map((e, i) => <li key={i} className="flex gap-2 text-[13px] leading-relaxed"><span className="mt-[7px] size-1 shrink-0 bg-signal" />{e}</li>) : <li className="text-[12px] text-faint">No evidence statements returned.</li>}
            </ul>
          </section>
          <section>
            <SectionLabel index="03">Historical events</SectionLabel>
            <div className="mt-2"><EventsTable rows={rows} onRow={openEvent} /></div>
            {rows.length > 0 && <p className="mt-1.5 font-mono text-[10px] text-faint">Select a row to open its extraction provenance.</p>}
          </section>
          {features.length > 0 && (
            <section>
              <SectionLabel index="04">Contributing features</SectionLabel>
              <div className="mt-2 grid grid-cols-2 gap-px border border-line bg-line sm:grid-cols-3" data-testid="why-features">
                {features.map(([k, v]) => (
                  <div key={k} className="bg-panel px-2.5 py-2"><div className="label">{humanize(k)}</div><div className="mt-0.5 truncate font-mono text-[12px] tnum"><Value v={v} /></div></div>
                ))}
              </div>
            </section>
          )}
          <section className="grid grid-cols-2 gap-6">
            <div>
              <SectionLabel index="05">Methodology</SectionLabel>
              <p className="mt-2 font-mono text-[12px]" data-testid="why-methodology">{humanize(r.assessment?.methodology ?? (r.alert?.context.methodology as string) ?? (r.rule ? "deterministic_rule" : "—"))}</p>
            </div>
            <div>
              <SectionLabel index="06">Rule source</SectionLabel>
              <div className="mt-2 flex flex-wrap gap-1.5" data-testid="why-rule-source">
                {[...new Set([r.rule?.rule_type, r.assessment?.model_or_rule_source, ...(r.alert?.provenance ?? [])].filter(Boolean) as string[])].map((s) => <Tag key={s}>{s}</Tag>)}
              </div>
            </div>
          </section>
          <section>
            <SectionLabel index="07">Limitations</SectionLabel>
            <ul className="mt-2 space-y-1" data-testid="why-limitations">
              {limitations.length ? limitations.map((l, i) => <li key={i} className="flex gap-2 text-[12px] text-dim"><span className="text-warn">!</span>{l}</li>) : <li className="text-[12px] text-faint">No limitations returned for this record.</li>}
            </ul>
          </section>
          <section>
            <SectionLabel index="08">Recommended action</SectionLabel>
            <div data-testid="why-recommended-action" className="mt-2 border-l-2 border-signal bg-panel2 px-3 py-2.5 text-[13px] leading-relaxed">
              {r.alert?.recommended_action ?? <span className="text-faint">No alert raised for this category — no action issued.</span>}
            </div>
            {r.alert && <p className="mt-1 font-mono text-[10px] text-faint">Static, human-authored recommendation from the rule catalogue — never LLM-generated.</p>}
          </section>
        </div>
      )}
    </Drawer>
  );
}
