import { useEffect, useRef, useState } from "react";
import { ArrowUp, Braces, Link2, Link2Off } from "lucide-react";
import type { StructuredIntent } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { useAskAI, useStructuredQuery } from "@/hooks/useQueryAI";
import { useAssessmentParams } from "@/hooks/useWellState";
import { useWorkspace } from "@/state/WorkspaceContext";
import { logSessionEvent } from "@/lib/sessionLog";
import { cn } from "@/lib/utils";
import { PrimaryButton, ToolButton } from "@/components/nwis/Panel";
import { ErrorState, SkeletonLines } from "@/components/nwis/States";
import { ApiError } from "@/api/client";
import { useInvestigations } from "./InvestigationStore";
import { QueryResult } from "./QueryResult";
import { SUGGESTED_QUESTIONS, withWellContext } from "./aiUtils";

const INTENTS: { id: StructuredIntent; label: string; needsWell: boolean }[] = [
  { id: "well_information", label: "Well information", needsWell: true },
  { id: "similar_wells", label: "Similar wells", needsWell: true },
  { id: "geological_context", label: "Geological context", needsWell: true },
  { id: "formation_information", label: "Formations", needsWell: true },
  { id: "document_search", label: "Document search", needsWell: false },
];

function StructuredForm({ initialText, onDone }: { initialText: string; onDone: () => void }) {
  const p = useAssessmentParams();
  const { user } = useAuth();
  const store = useInvestigations();
  const run = useStructuredQuery();
  const [intent, setIntent] = useState<StructuredIntent>("geological_context");
  const [text, setText] = useState(initialText);
  const def = INTENTS.find((i) => i.id === intent)!;
  const canRun = def.needsWell ? !!p.ref : text.trim().length > 0;

  const submit = () => {
    const query = def.needsWell
      ? { intent, target_dataset: p.ref!.dataset, target_well_id: p.ref!.well_id }
      : { intent, search_text: text.trim().slice(0, 500), top_k: 5 };
    const label = def.needsWell ? `${def.label} · ${p.ref!.well_id}` : `${def.label} · “${text.trim()}”`;
    run.mutate({ query, label }, {
      onSuccess: (inv) => { store.add(inv); logSessionEvent(user?.employeeId ?? "?", "Structured query", intent, "Allowed", inv.meta.requestId); onDone(); },
    });
  };

  return (
    <div data-testid="structured-query-form" className="space-y-2 border border-line bg-panel2 p-2.5">
      <div className="flex items-center gap-2"><Braces className="size-3.5 text-signal" /><span className="label text-dim">Deterministic query · POST /query/structured · no LLM</span></div>
      <div className="flex flex-wrap gap-1">
        {INTENTS.map((i) => (
          <button key={i.id} type="button" data-testid={`structured-intent-${i.id}`} onClick={() => setIntent(i.id)} className={cn("h-6 border px-2 font-mono text-[10px]", intent === i.id ? "border-signal/60 text-signal" : "border-line text-dim hover:text-ink")}>{i.label}</button>
        ))}
      </div>
      {def.needsWell ? (
        <p className="font-mono text-[10px] text-faint">target · {p.ref ? `${p.ref.dataset}:${p.ref.well_id}` : "select a current well"}</p>
      ) : (
        <input data-testid="structured-search-text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search text" className="h-7 w-full border border-line bg-panel px-2 text-[12px] outline-none focus:border-signal/60" />
      )}
      <div className="flex items-center gap-2">
        <PrimaryButton testid="structured-run-btn" disabled={!canRun || run.isPending} onClick={submit}>{run.isPending ? "Running…" : "Run query"}</PrimaryButton>
        <button type="button" onClick={onDone} className="font-mono text-[10px] uppercase text-faint hover:text-ink">Cancel</button>
      </div>
      {run.isError && <ErrorState error={run.error} />}
    </div>
  );
}

export function IntelligencePanel({ showHistory = false }: { showHistory?: boolean }) {
  const ws = useWorkspace();
  const p = useAssessmentParams();
  const { user } = useAuth();
  const store = useInvestigations();
  const ask = useAskAI();
  const [q, setQ] = useState("");
  const [attach, setAttach] = useState(true);
  const [structured, setStructured] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (ws.aiDraft) {
      setQ(ws.aiDraft);
      ws.setAiDraft(null);
      input.current?.focus();
    }
  }, [ws.aiDraft, ws]);

  const sent = attach ? withWellContext(q.trim(), p.ref, p.depth) : q.trim();
  const submit = () => {
    if (!q.trim() || ask.isPending) return;
    ask.mutate(sent, {
      onSuccess: (inv) => { store.add(inv); logSessionEvent(user?.employeeId ?? "?", "AI query", "POST /query", inv.response.errors.length ? "Failed" : "Allowed", inv.meta.requestId); },
    });
  };
  const nlUnavailable = ask.error instanceof ApiError && ask.error.status === 503;

  return (
    <div data-testid="intelligence-panel" className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 space-y-2 border-b border-line p-3">
        <p className="text-[12px] text-dim">Ask about wells, drilling events, geological context and risk.</p>
        <div className="border border-line bg-panel2 transition-colors focus-within:border-signal/60">
          <textarea
            ref={input}
            data-testid="ai-question-input"
            value={q}
            rows={2}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder="What happened in nearby wells around my current depth?"
            className="block w-full resize-none bg-transparent px-2.5 py-2 text-[13px] leading-relaxed text-ink outline-none placeholder:text-faint"
          />
          <div className="flex items-center gap-2 border-t border-line-soft px-2 py-1.5">
            <button type="button" data-testid="ai-attach-context-toggle" onClick={() => setAttach(!attach)} title="Append current-well context to the question" className={cn("flex items-center gap-1 font-mono text-[10px]", attach ? "text-signal" : "text-faint")}>
              {attach ? <Link2 className="size-3" /> : <Link2Off className="size-3" />}{attach && p.ref ? `${p.ref.well_id}${p.depth != null ? ` @ ${Math.round(p.depth)} m` : ""}` : "no well context"}
            </button>
            <button type="button" data-testid="ai-structured-toggle" onClick={() => setStructured(!structured)} className="ml-auto font-mono text-[10px] uppercase tracking-[0.08em] text-faint hover:text-ink">Structured</button>
            <button type="button" data-testid="ai-submit-btn" disabled={!q.trim() || ask.isPending} onClick={submit} className="flex size-7 items-center justify-center bg-signal text-[#061014] transition-colors hover:bg-[#5ad6e5] disabled:bg-raised disabled:text-faint"><ArrowUp className="size-4" /></button>
          </div>
        </div>
        {attach && q.trim() && sent !== q.trim() && <p className="font-mono text-[10px] leading-relaxed text-faint" data-testid="ai-sent-preview">sends · {sent}</p>}
        {!q && !ask.isPending && (
          <div className="flex flex-col gap-1" data-testid="ai-suggestions">
            {SUGGESTED_QUESTIONS.map((s, i) => (
              <button key={s} type="button" data-testid={`ai-suggestion-${i}`} onClick={() => { setQ(s); input.current?.focus(); }} className="truncate text-left text-[12px] text-dim transition-colors hover:text-signal">→ {s}</button>
            ))}
          </div>
        )}
        {structured && <StructuredForm initialText={q} onDone={() => setStructured(false)} />}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {ask.isPending && <SkeletonLines rows={6} label="Running query graph · interpret → resolve → evidence → confidence" />}
        {ask.isError && (
          <div>
            <ErrorState error={ask.error} context={nlUnavailable ? "AI service is currently unavailable. The operational well and risk information remains available." : "NWIS Intelligence request failed."} />
            <div className="px-3"><ToolButton testid="ai-error-fallback-btn" onClick={() => setStructured(true)}>Use deterministic query</ToolButton></div>
          </div>
        )}
        {!ask.isPending && store.active && <QueryResult inv={store.active} onFollowUp={() => input.current?.focus()} onFallback={() => setStructured(true)} />}
        {!ask.isPending && !store.active && !ask.isError && (
          <div className="flex h-full flex-col justify-end gap-1 pb-2 text-faint">
            <span className="label">No investigation yet</span>
            <p className="text-[12px]">Answers include evidence, rationale, a heuristic confidence value and provenance. The language model only interprets the question; it never writes answers or SQL.</p>
          </div>
        )}
        {showHistory && store.items.length > 1 && (
          <div className="mt-6 border-t border-line pt-3">
            <span className="label">Session investigations</span>
            <ul className="mt-2 space-y-1">
              {store.items.map((i) => (
                <li key={i.id}><button type="button" onClick={() => store.setActive(i.id)} className={cn("w-full truncate text-left text-[12px]", i.id === store.active?.id ? "text-signal" : "text-dim hover:text-ink")}>{i.question}</button></li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
