import { Panel } from "@/components/nwis/Panel";
import { Tag } from "@/components/nwis/Tags";
import { IntelligencePanel } from "@/features/ai/IntelligencePanel";
import { useInvestigations } from "@/features/ai/InvestigationStore";
import { WorkspaceMap } from "@/features/map/WorkspaceMap";
import { cn } from "@/lib/utils";

export default function AssistantPage() {
  const store = useInvestigations();
  return (
    <div data-testid="assistant-page" className="grid h-full min-h-[640px] grid-cols-1 gap-1.5 p-1.5 lg:grid-cols-[240px_minmax(420px,600px)_minmax(0,1fr)]">
      <Panel code="07.1" title="Investigations" meta={`${store.items.length} this session`} testid="ai-history-panel" className="hidden lg:flex">
        {store.items.length === 0 ? <p className="p-3 text-[12px] text-faint">Questions asked this session appear here.</p> : (
          <ul className="divide-y divide-line-soft">
            {store.items.map((i, n) => (
              <li key={i.id}>
                <button type="button" data-testid={`ai-history-item-${n}`} onClick={() => store.setActive(i.id)} className={cn("w-full px-3 py-2 text-left transition-colors hover:bg-panel2", i.id === store.active?.id && "bg-panel2")}>
                  <div className="flex items-center gap-1.5">
                    <Tag tone={i.response.errors.length ? "crit" : "ok"}>{i.response.errors.length ? "errors" : "ok"}</Tag>
                    <span className="font-mono text-[9px] text-faint">{i.askedAt.slice(11, 19)}</span>
                  </div>
                  <div className={cn("mt-1 line-clamp-2 text-[12px]", i.id === store.active?.id ? "text-ink" : "text-dim")}>{i.question}</div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel code="07" title="NWIS Intelligence" testid="ai-main-panel" bodyClassName="overflow-hidden"><IntelligencePanel /></Panel>
      <WorkspaceMap compact className="min-h-[420px]" />
    </div>
  );
}
