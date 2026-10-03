import type { RiskAssessment } from "@/api/types";
import { fmtScore, riskLabel } from "@/lib/format";
import { LevelTag, toneForLevel } from "@/components/nwis/Tags";
import { Meter, ThinBar } from "@/components/nwis/Meter";
import { cn } from "@/lib/utils";
import { meterTone } from "./RiskMatrix";

export function RiskCard({ a, onWhy }: { a: RiskAssessment; onWhy: () => void }) {
  const tone = toneForLevel(a.level);
  const events = Number(a.contributing_features.event_count ?? 0);
  const wells = Number(a.contributing_features.distinct_wells ?? 0);
  return (
    <article data-testid={`risk-card-${a.risk_type}`} className={cn("flex min-w-0 flex-col border bg-panel", tone === "crit" ? "border-crit/40" : tone === "warn" ? "border-warn/40" : "border-line")}>
      <header className="border-b border-line px-3 py-2">
        <div className="font-semicond text-[11px] font-semibold uppercase tracking-[0.14em] text-dim">{riskLabel(a.risk_type)} risk</div>
      </header>
      <div className="flex flex-1 flex-col gap-3 px-3 py-3">
        <div className="flex items-end justify-between">
          <LevelTag level={a.level} className="h-6 text-[11px]" />
          <div className="text-right">
            <div className="font-mono text-[22px] leading-none tnum text-ink">{fmtScore(a.score)}</div>
            <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.1em] text-faint">risk score</div>
          </div>
        </div>
        <Meter value={a.score} tone={meterTone(a.level)} segments={24} />
        <div>
          <div className="flex justify-between font-mono text-[10px]"><span className="text-faint">CONFIDENCE</span><span className="tnum text-dim">{a.confidence.toFixed(2)}</span></div>
          <ThinBar value={a.confidence} tone="signal" className="mt-1" />
        </div>
        <p className="line-clamp-3 text-[12px] leading-relaxed text-dim">{a.evidence[0] ?? "No supporting evidence returned."}</p>
        <div className="mt-auto flex items-center justify-between border-t border-line-soft pt-2">
          <span className="font-mono text-[10px] text-faint">{events} evt · {wells} well{wells === 1 ? "" : "s"}</span>
          <button type="button" data-testid={`risk-card-why-${a.risk_type}`} onClick={onWhy} className="border border-signal/40 px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-signal transition-colors hover:bg-signal-deep">Why?</button>
        </div>
      </div>
    </article>
  );
}
