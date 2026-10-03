import { useState } from "react";
import { FileText, Search } from "lucide-react";
import type { DocumentSearchRequest } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { useDocumentSearch, useDocumentsMetadata } from "@/hooks/useDocuments";
import { useWorkspace } from "@/state/WorkspaceContext";
import { logSessionEvent } from "@/lib/sessionLog";
import { Panel, PrimaryButton, ToolButton } from "@/components/nwis/Panel";
import { Tag } from "@/components/nwis/Tags";
import { ThinBar } from "@/components/nwis/Meter";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/nwis/States";
import { HandwritingTag } from "@/features/documents/DocumentDrawer";

const SOURCES = [undefined, "pdf", "text", "image"] as const;

export default function DocumentsPage() {
  const { user } = useAuth();
  const { openDrawer } = useWorkspace();
  const search = useDocumentSearch();
  const [q, setQ] = useState("");
  const [topK, setTopK] = useState(10);
  const [source, setSource] = useState<DocumentSearchRequest["source_type"]>();
  const results = search.data?.results ?? [];
  const ids = [...new Set(results.map((r) => r.document_id))];
  const metas = useDocumentsMetadata(ids);
  const metaById = new Map(metas.filter((m) => m.data).map((m) => [m.data!.document_id, m.data!]));

  const submit = () => {
    if (!q.trim()) return;
    search.mutate({ query: q.trim(), top_k: topK, source_type: source }, {
      onSettled: (d, err) => logSessionEvent(user?.employeeId ?? "?", "Document search", "POST /documents/search", err ? "Failed" : "Allowed"),
    });
  };

  return (
    <div data-testid="documents-page" className="flex min-h-full flex-col gap-1.5 p-1.5 xl:h-full">
      <div className="border border-line bg-panel p-3">
        <div className="flex items-center gap-2">
          <span className="font-semicond text-[12px] font-semibold uppercase tracking-[0.14em]">Knowledge vault</span>
          <Tag tone="info">Authorized operational data</Tag>
          <span className="ml-auto font-mono text-[10px] text-faint">semantic search · 384-dim document embeddings · separate from well vectors</span>
        </div>
        <form className="mt-2.5 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <label className="flex h-9 min-w-[320px] flex-1 items-center gap-2 border border-line bg-panel2 px-3 focus-within:border-signal/60">
            <Search className="size-4 text-faint" />
            <input data-testid="document-search-input" value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} placeholder="Search technical knowledge…" className="w-full bg-transparent text-[13px] outline-none placeholder:text-faint" />
          </label>
          <div className="flex items-center gap-1">
            {SOURCES.map((s) => <ToolButton key={s ?? "any"} testid={`document-source-${s ?? "any"}`} active={source === s} onClick={() => setSource(s)}>{s ?? "Any source"}</ToolButton>)}
          </div>
          <select data-testid="document-topk-select" value={topK} onChange={(e) => setTopK(Number(e.target.value))} className="h-9 border border-line bg-panel2 px-2 font-mono text-[11px] text-dim">
            {[5, 10, 20, 50].map((n) => <option key={n} value={n}>top {n}</option>)}
          </select>
          <PrimaryButton type="submit" testid="document-search-btn" disabled={!q.trim() || search.isPending} className="h-9">Search</PrimaryButton>
        </form>
      </div>

      <Panel code="08" title="Results" meta={search.data ? `${search.data.count} passages · “${search.data.query}”` : undefined} testid="document-results-panel" className="min-h-[360px] flex-1">
        {search.isPending ? <SkeletonLines rows={8} label="Embedding query and searching document chunks" /> :
          search.isError ? <ErrorState error={search.error} context="Document search failed. The first document query can be slow while the embedding model loads on the server." onRetry={submit} /> :
          !search.data ? <EmptyState title="No search yet" hint="Results show file, page, section and similarity for every passage, so each fact remains traceable to its source page." icon={<FileText className="size-3.5" />} /> :
          !results.length ? <EmptyState title="No matching passages" testid="documents-empty" /> : (
          <ul className="divide-y divide-line-soft" data-testid="document-results">
            {results.map((r, i) => {
              const meta = metaById.get(r.document_id);
              const page = meta?.pages.find((p) => p.page_number === r.page_number);
              return (
                <li key={r.chunk_id} className="grid grid-cols-[48px_minmax(0,1fr)_140px] gap-3 px-3 py-3">
                  <div className="font-mono text-[11px] text-faint">#{r.rank}</div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-mono text-[12px] text-ink">{r.file_name}</span>
                      <span className="font-mono text-[10px] text-faint">page {r.page_number ?? "—"} · {r.section ?? "no section"}</span>
                      <HandwritingTag cls={page?.handwriting_classification} />
                      {page?.used_ocr && <Tag className="border-dashed text-dim">OCR</Tag>}
                    </div>
                    <p className="mt-1.5 line-clamp-3 text-[13px] leading-relaxed text-dim">“{r.text}”</p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="w-full">
                      <div className="flex justify-between font-mono text-[10px]"><span className="text-faint">similarity</span><span className="tnum">{r.similarity.toFixed(3)}</span></div>
                      <ThinBar value={r.similarity} className="mt-1" />
                    </div>
                    <ToolButton testid={`document-open-btn-${i}`} onClick={() => openDrawer({ kind: "document", documentId: r.document_id, chunk: r })}>Open document</ToolButton>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
