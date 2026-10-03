import { HelpCircle } from "lucide-react";
import type { RiskAssessment } from "@/api/types";
import { useRiskAssessment } from "@/hooks/useRisk";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtScore, RISK_ORDER, riskLabel } from "@/lib/format";
import { LevelTag, toneForLevel } from "@/components/nwis/Tags";
import { Meter } from "@/components/nwis/Meter";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/nwis/States";

export const sortRisks = (a: RiskAssessment[]) => [...a].sort((x, y) => RISK_ORDER.indexOf(x.risk_type) - RISK_ORDER.indexOf(y.risk_type));
export const meterTone = (level: string) => ({ crit: "crit", warn: "warn" } as const)[toneForLevel(level) as "crit" | "warn"] ?? "dim";

function RiskRow({ a, onWhy }: { a: RiskAssessment; onWhy: () => void }) {
  const events = Number(a.contributing_features.event_count ?? a.historical_events.length ?? 0);
  return (
    <button type="button" data-testid={`risk-row-${a.risk_type}`} onClick={onWhy} className="group grid w-full grid-cols-[minmax(92px,1.1fr)_58px_minmax(70px,1fr)_44px_38px_18px] items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-panel2">
      <span className="truncate text-[12px] font-medium uppercase tracking-[0.04em] font-semicond">{riskLabel(a.risk_type)}</span>
      <LevelTag level={a.level} />
      <div>
        <Meter value={a.score} tone={meterTone(a.level)} segments={16} />
        <div className="mt-1 flex justify-between font-mono text-[9px] text-faint"><span>score</span><span className="text-dim tnum">{fmtScore(a.score)}</span></div>
      </div>
      <div className="text-right">
        <div className="font-mono text-[11px] tnum text-dim">{a.confidence.toFixed(2)}</div>
        <div className="font-mono text-[9px] text-faint">conf</div>
      </div>
      <div className="text-right">
        <div className="font-mono text-[11px] tnum text-dim">{events}</div>
        <div className="font-mono text-[9px] text-faint">evts</div>
      </div>
      <HelpCircle className="size-3.5 text-faint transition-colors group-hover:text-signal" />
    </button>
  );
}

export function RiskMatrix() {
  const { currentWell, openDrawer } = useWorkspace();
  const risk = useRiskAssessment();
  if (!currentWell) return <EmptyState title="No current well" hint="Risk is assessed against the current well's depth and offsets." />;
  if (risk.isLoading) return <SkeletonLines rows={5} label="Risk assessment" />;
  if (risk.isError) return <ErrorState error={risk.error} context="Risk assessment failed." onRetry={() => risk.refetch()} />;
  const items = sortRisks(risk.data?.assessments ?? []);
  if (!items.length) return <EmptyState title="No assessments returned" />;
  return (
    <div data-testid="risk-matrix" className="divide-y divide-line-soft">
      {items.map((a) => <RiskRow key={a.risk_type} a={a} onWhy={() => openDrawer({ kind: "risk", riskType: a.risk_type })} />)}
      <p className="px-3 py-2 font-mono text-[10px] leading-relaxed text-faint">
        Rule-based evidence score · not a calibrated probability · {risk.data?.correlated_event_count ?? 0} correlated events
      </p>
    </div>
  );
}
