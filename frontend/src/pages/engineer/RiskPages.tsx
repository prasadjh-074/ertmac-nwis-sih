import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useRiskAssessment } from "@/hooks/useRisk";
import { useAssessmentParams } from "@/hooks/useWellState";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtDepth, humanize, riskLabel } from "@/lib/format";
import { Panel } from "@/components/nwis/Panel";
import { LevelTag, Tag } from "@/components/nwis/Tags";
import { EmptyState, ErrorState, SkeletonBlock, SkeletonLines } from "@/components/nwis/States";
import { RiskCard } from "@/features/risk/RiskCard";
import { sortRisks } from "@/features/risk/RiskMatrix";
import { AlertList } from "@/features/risk/AlertList";

function RulesTable() {
  const risk = useRiskAssessment();
  if (risk.isLoading) return <SkeletonLines rows={5} />;
  if (risk.isError) return <ErrorState error={risk.error} />;
  const rules = risk.data?.rules ?? [];
  if (!rules.length) return <EmptyState title="No rules evaluated" />;
  return (
    <table className="w-full text-left text-[12px]" data-testid="rules-table">
      <thead className="sticky top-0 bg-panel font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
        <tr className="border-b border-line"><th className="px-3 py-1.5">Rule</th><th>State</th><th>Severity</th><th>Evidence</th></tr>
      </thead>
      <tbody className="divide-y divide-line-soft">
        {rules.map((r) => (
          <tr key={r.rule_type} data-testid={`rule-row-${r.rule_type}`}>
            <td className="px-3 py-1.5 font-mono text-[11px]">{r.rule_type}</td>
            <td>{r.triggered ? <Tag tone="warn">Triggered</Tag> : <Tag>Not triggered</Tag>}</td>
            <td><LevelTag level={r.severity} /></td>
            <td className="py-1.5 pr-3 text-dim">{r.evidence.join(" ") || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ScoreConfidenceChart() {
  const risk = useRiskAssessment();
  if (risk.isLoading) return <SkeletonBlock className="m-3 h-[220px]" />;
  if (!risk.data) return null;
  const data = sortRisks(risk.data.assessments).map((a) => ({ name: riskLabel(a.risk_type), score: a.score, confidence: a.confidence }));
  return (
    <div className="h-full min-h-[240px] p-2" data-testid="risk-score-confidence-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 20, left: 8, bottom: 4 }} barGap={2}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="2 4" horizontal={false} />
          <XAxis type="number" domain={[0, 1]} stroke="#5b687b" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
          <YAxis type="category" dataKey="name" width={120} stroke="#5b687b" tick={{ fontSize: 11, fill: "#94a1b4" }} />
          <Tooltip cursor={{ fill: "rgba(46,197,216,0.05)" }} contentStyle={{ background: "#0d1219", border: "1px solid #1e293b", fontFamily: "IBM Plex Mono", fontSize: 11 }} formatter={(v: number) => v.toFixed(3)} />
          <Legend wrapperStyle={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
          <Bar dataKey="score" name="risk score" fill="#f0a63a" barSize={8} />
          <Bar dataKey="confidence" name="confidence" fill="#2ec5d8" barSize={8} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RiskPage() {
  const { currentWell, openDrawer } = useWorkspace();
  const risk = useRiskAssessment();
  const p = useAssessmentParams();
  return (
    <div data-testid="risk-page" className="flex min-h-full flex-col gap-1.5 p-1.5 xl:h-full">
      <div className="flex flex-wrap items-center gap-3 border border-line bg-panel px-3 py-2">
        <span className="font-semicond text-[12px] font-semibold uppercase tracking-[0.14em]">Risk intelligence</span>
        <span className="font-mono text-[10px] text-faint">{currentWell?.well_id ?? "—"} · depth {fmtDepth(p.depth)} · formation {p.formation ?? "not resolved"} · {risk.data?.correlated_event_count ?? "…"} correlated events</span>
        <Tag className="ml-auto border-dashed">Evidence-based rule assessment · not a probability</Tag>
      </div>
      {!currentWell ? <EmptyState title="No current well" /> : risk.isError ? <ErrorState error={risk.error} onRetry={() => risk.refetch()} /> : (
        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5" data-testid="risk-cards">
          {risk.isLoading ? Array.from({ length: 5 }).map((_, i) => <SkeletonBlock key={i} className="h-[250px]" />) :
            sortRisks(risk.data?.assessments ?? []).map((a) => <RiskCard key={a.risk_type} a={a} onWhy={() => openDrawer({ kind: "risk", riskType: a.risk_type })} />)}
        </div>
      )}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-1.5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Panel code="05.2" title="Score vs confidence" meta="is a score backed by evidence?" testid="risk-chart-panel" className="min-h-[260px]"><ScoreConfidenceChart /></Panel>
        <Panel code="05.3" title="Deterministic rules" meta={risk.data ? `${risk.data.rules.filter((r) => r.triggered).length} triggered / ${risk.data.rules.length}` : undefined} testid="risk-rules-panel" className="min-h-[260px]"><RulesTable /></Panel>
      </div>
    </div>
  );
}

export function AlertsPage() {
  const risk = useRiskAssessment();
  return (
    <div data-testid="alerts-page" className="grid min-h-full grid-cols-1 gap-1.5 p-1.5 lg:h-full lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <Panel code="06" title="Risk alerts" meta="select an alert to see why it was raised" testid="alerts-panel" className="min-h-[400px]"><AlertList /></Panel>
      <Panel code="06.1" title="How alerts are produced" testid="alerts-method-panel">
        <div className="space-y-3 p-3 text-[12px] leading-relaxed text-dim">
          <p>Alerts derive from two backend sources: risk assessments scored above LOW, and deterministic rules that trigger on correlated offset-well history.</p>
          <p>Recommended actions come from a static, human-authored catalogue. They are never generated by a language model.</p>
          <div className="border-t border-line pt-3">
            <div className="label mb-2">Rule catalogue state · this context</div>
            {risk.isLoading ? <SkeletonLines rows={4} className="px-0" /> : (risk.data?.rules ?? []).map((r) => (
              <div key={r.rule_type} className="flex items-center justify-between py-0.5 font-mono text-[11px]"><span>{humanize(r.rule_type)}</span><span className={r.triggered ? "text-warn" : "text-faint"}>{r.triggered ? "TRIGGERED" : "idle"}</span></div>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  );
}
