import type { DocumentChunk } from "@/api/types";
import { useDocumentMetadata } from "@/hooks/useDocuments";
import { useWorkspace } from "@/state/WorkspaceContext";
import { fmtNum, humanize } from "@/lib/format";
import { Drawer } from "@/components/nwis/Drawer";
import { KV, SectionLabel } from "@/components/nwis/Panel";
import { Tag } from "@/components/nwis/Tags";
import { ErrorState, SkeletonLines } from "@/components/nwis/States";
import { cn } from "@/lib/utils";

export function HandwritingTag({ cls }: { cls: string | null | undefined }) {
  if (cls !== "handwritten" && cls !== "mixed") return null;
  return <Tag className="border-dashed text-dim" testid="handwriting-tag">{cls === "mixed" ? "Mixed handwriting" : "Handwritten"}</Tag>;
}

export function DocumentDrawer({ documentId, chunk }: { documentId: string; chunk?: DocumentChunk }) {
  const { closeDrawer } = useWorkspace();
  const meta = useDocumentMetadata(documentId);
  const d = meta.data;
  return (
    <Drawer open onClose={closeDrawer} testid="document-drawer" kicker="Document · authorized operational data" title={<h2 className="break-all font-mono text-[16px]">{d?.file_name ?? chunk?.file_name ?? documentId}</h2>}>
      {meta.isLoading ? <SkeletonLines rows={6} /> : meta.isError ? <ErrorState error={meta.error} /> : d && (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-4">
            <KV label="Source type" value={d.source_type} />
            <KV label="Pages" value={d.page_count ?? "—"} />
            <KV label="Handwriting pages" value={`${d.handwriting_page_count}`} />
          </div>
          {chunk && (
            <section>
              <SectionLabel index="01">Matched passage</SectionLabel>
              <div className="mt-2 font-mono text-[10px] text-faint">page {chunk.page_number ?? "—"} · chunk {chunk.chunk_index} · {chunk.section ?? "no section"} · similarity {chunk.similarity.toFixed(3)}</div>
              <blockquote className="mt-1.5 border-l-2 border-signal bg-panel2 px-3 py-2.5 text-[13px] leading-relaxed">{chunk.text}</blockquote>
            </section>
          )}
          <section>
            <SectionLabel index={chunk ? "02" : "01"}>Page provenance</SectionLabel>
            <div className="mt-2 overflow-x-auto border border-line">
              <table className="w-full text-left text-[12px]" data-testid="document-pages-table">
                <thead className="bg-panel2 font-mono text-[10px] uppercase tracking-[0.08em] text-faint">
                  <tr><th className="px-2 py-1.5">Page</th><th className="px-2">Content</th><th className="px-2">OCR</th><th className="px-2">OCR conf.</th><th className="px-2">Handwriting</th><th className="px-2">HW conf.</th><th className="px-2">HW OCR</th></tr>
                </thead>
                <tbody className="divide-y divide-line-soft font-mono">
                  {d.pages.map((p) => (
                    <tr key={p.page_number} className={cn(chunk?.page_number === p.page_number && "bg-signal-deep/40")}>
                      <td className="px-2 py-1.5">{p.page_number}</td>
                      <td className="px-2">{p.source_content_type ?? "—"}</td>
                      <td className="px-2">{p.used_ocr ? "yes" : "no"}</td>
                      <td className="px-2 tnum">{fmtNum(p.ocr_confidence, 2)}</td>
                      <td className="px-2">{humanize(p.handwriting_classification)}</td>
                      <td className="px-2 tnum">{fmtNum(p.handwriting_confidence, 2)}</td>
                      <td className="px-2">{humanize(p.handwriting_ocr_status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-1.5 font-mono text-[10px] text-faint">Handwriting classification is ingestion metadata. Handwritten text is not transcribed unless a handwriting OCR provider was available.</p>
          </section>
        </div>
      )}
    </Drawer>
  );
}
