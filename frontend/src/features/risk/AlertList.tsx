import { ChevronRight } from "lucide-react";
import { useRiskAlerts } from "@/hooks/useAlerts";
import { useWorkspace } from "@/state/WorkspaceContext";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { LevelTag, toneForLevel } from "@/components/nwis/Tags";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/nwis/States";

export function AlertList({ dense = false }: { dense?: boolean }) {
  const { currentWell, openDrawer } = useWorkspace();
  const alerts = useRiskAlerts();
  if (!currentWell) return <EmptyState title="No current well" />;
  if (alerts.isLoading) return <SkeletonLines rows={4} label="Evaluating alert rules" />;
  if (alerts.isError) return <ErrorState error={alerts.error} context="Alerts could not be generated." onRetry={() => alerts.refetch()} />;
  const list = alerts.data?.alerts ?? [];
  if (!list.length) return <EmptyState title="No alerts raised" hint="No assessment above LOW and no deterministic rule triggered for this context." testid="alerts-empty" />;
  return (
    <ul data-testid="alert-list" className="divide-y divide-line-soft">
      {list.map((a, i) => {
        const tone = toneForLevel(a.severity);
        return (
          <li key={`${a.alert_id}-${i}`}>
            <button type="button" data-testid={`alert-item-${i}`} onClick={() => openDrawer({ kind: "alert", alert: a })} className="group relative flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-panel2">
              <span className={cn("absolute inset-y-0 left-0 w-[2px]", tone === "crit" ? "bg-crit" : tone === "warn" ? "bg-warn" : "bg-faint")} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <LevelTag level={a.severity} />
                  <span className="truncate font-semicond text-[12px] font-semibold uppercase tracking-[0.06em]">{a.title}</span>
                </div>
                {!dense && <p className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-dim">{a.explanation}</p>}
                <div className="mt-1 font-mono text-[10px] text-faint">source · {a.provenance.map(humanize).join(", ") || "—"}</div>
              </div>
              <span className="mt-1 flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-faint transition-colors group-hover:text-signal">Why <ChevronRight className="size-3" /></span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
