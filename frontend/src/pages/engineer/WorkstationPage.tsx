import { useState } from "react";
import { Bot } from "lucide-react";
import { Panel } from "@/components/nwis/Panel";
import { Drawer } from "@/components/nwis/Drawer";
import { WorkspaceMap } from "@/features/map/WorkspaceMap";
import { RiskMatrix } from "@/features/risk/RiskMatrix";
import { AlertList } from "@/features/risk/AlertList";
import { EventTimeline } from "@/features/events/EventTimeline";
import { IntelligencePanel } from "@/features/ai/IntelligencePanel";
import { useRiskAlerts } from "@/hooks/useAlerts";
import { useAssessmentParams } from "@/hooks/useWellState";
import { fmtDepth } from "@/lib/format";

export default function WorkstationPage() {
  const [aiOpen, setAiOpen] = useState(false);
  const alerts = useRiskAlerts();
  const p = useAssessmentParams();
  return (
    <div data-testid="workstation" className="grid min-h-full grid-cols-1 gap-1.5 p-1.5 xl:h-full xl:grid-cols-[minmax(0,1fr)_minmax(340px,400px)]">
      <div className="grid min-h-0 grid-rows-[minmax(380px,1fr)_auto] gap-1.5 xl:grid-rows-[minmax(300px,1fr)_minmax(240px,37%)]">
        <WorkspaceMap />
        <div className="grid min-h-0 grid-cols-1 gap-1.5 lg:grid-cols-[1.2fr_1fr_0.95fr]">
          <Panel code="R-01" title="Risk intelligence" meta={p.ref ? `@ ${fmtDepth(p.depth)}` : undefined} testid="ws-risk-panel" className="max-h-[420px] xl:max-h-none">
            <RiskMatrix />
          </Panel>
          <Panel code="A-02" title="Alerts" meta={alerts.data ? `${alerts.data.count} raised` : undefined} testid="ws-alerts-panel" className="max-h-[420px] xl:max-h-none">
            <AlertList />
          </Panel>
          <Panel code="E-03" title="Drilling history" meta="own + correlated" testid="ws-events-panel" className="max-h-[420px] xl:max-h-none">
            <EventTimeline compact />
          </Panel>
        </div>
      </div>
      <Panel code="AI" title="NWIS Intelligence" testid="ws-ai-panel" className="hidden xl:flex" bodyClassName="overflow-hidden">
        <IntelligencePanel />
      </Panel>

      <button type="button" data-testid="ws-ai-open-btn" onClick={() => setAiOpen(true)} className="fixed bottom-4 right-4 z-30 flex h-10 items-center gap-2 border border-signal/50 bg-panel px-4 font-mono text-[11px] uppercase tracking-[0.12em] text-signal xl:hidden">
        <Bot className="size-4" /> NWIS Intelligence
      </button>
      <Drawer open={aiOpen} onClose={() => setAiOpen(false)} kicker="AI" title={<h2 className="font-semicond text-[16px] font-semibold uppercase tracking-[0.1em]">NWIS Intelligence</h2>} width="w-[min(460px,100vw)]">
        <div className="-mx-5 -my-4 h-[calc(100%+2rem)]"><IntelligencePanel /></div>
      </Drawer>
    </div>
  );
}
