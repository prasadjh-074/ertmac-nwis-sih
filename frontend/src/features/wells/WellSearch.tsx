import { useMemo, useRef, useState } from "react";
import { MapPinOff, Search } from "lucide-react";
import type { WellLocation } from "@/api/types";
import { useWells } from "@/hooks/useWells";
import { useWorkspace } from "@/state/WorkspaceContext";
import { sameWell, wellKey } from "@/lib/format";
import { cn } from "@/lib/utils";

const DATASETS = ["ALL", "VOLVE", "FORCE_2020"] as const;

export function WellSearch({ className, autoFocus }: { className?: string; autoFocus?: boolean }) {
  const { data, isLoading, isError } = useWells();
  const { currentWell, setCurrentWell } = useWorkspace();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [dataset, setDataset] = useState<(typeof DATASETS)[number]>("ALL");
  const [coordsOnly, setCoordsOnly] = useState(false);
  const [field, setField] = useState("");
  const [cursor, setCursor] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);

  const fields = useMemo(() => [...new Set((data?.wells ?? []).map((w) => w.field_name).filter(Boolean) as string[])].sort(), [data]);
  const results = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (data?.wells ?? []).filter((w) =>
      (dataset === "ALL" || w.dataset === dataset) &&
      (!coordsOnly || w.has_coordinates) &&
      (!field || w.field_name === field) &&
      (!term || w.well_id.toLowerCase().includes(term) || (w.field_name ?? "").toLowerCase().includes(term) || (w.sodir_wellbore_name ?? "").toLowerCase().includes(term)),
    );
  }, [data, q, dataset, coordsOnly, field]);

  const pick = (w: WellLocation) => {
    setCurrentWell({ dataset: w.dataset, well_id: w.well_id });
    setOpen(false);
    setQ("");
  };

  return (
    <div ref={wrap} className={cn("relative", className)} onBlur={(e) => !wrap.current?.contains(e.relatedTarget as Node) && setOpen(false)}>
      <label className="flex h-8 items-center gap-2 border border-line bg-panel2 px-2.5 transition-colors focus-within:border-signal/60">
        <Search className="size-3.5 text-faint" />
        <input
          data-testid="well-search-input"
          autoFocus={autoFocus}
          value={q}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQ(e.target.value); setOpen(true); setCursor(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, results.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
            if (e.key === "Enter" && results[cursor]) pick(results[cursor]);
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder="Search wells · ID, field, wellbore"
          className="w-full bg-transparent font-mono text-[12px] text-ink outline-none placeholder:text-faint"
        />
        <span className="font-mono text-[10px] text-faint">{data ? data.count : isLoading ? "…" : "—"}</span>
      </label>

      {open && (
        <div data-testid="well-search-dropdown" tabIndex={-1} className="absolute right-0 top-9 z-40 w-[min(520px,90vw)] border border-line bg-panel shadow-[0_12px_40px_rgba(0,0,0,0.55)]">
          <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-2 py-2">
            {DATASETS.map((d) => (
              <button key={d} type="button" data-testid={`well-search-dataset-${d}`} onClick={() => setDataset(d)} className={cn("h-6 border px-2 font-mono text-[10px] tracking-[0.06em]", dataset === d ? "border-signal/60 text-signal" : "border-line text-dim hover:text-ink")}>{d}</button>
            ))}
            <select data-testid="well-search-field-select" value={field} onChange={(e) => setField(e.target.value)} className="h-6 max-w-[150px] border border-line bg-panel2 px-1 font-mono text-[10px] text-dim outline-none">
              <option value="">Any field</option>
              {fields.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <label className="ml-auto flex items-center gap-1.5 font-mono text-[10px] text-dim">
              <input type="checkbox" data-testid="well-search-coords-only" checked={coordsOnly} onChange={(e) => setCoordsOnly(e.target.checked)} className="accent-[#2ec5d8]" />
              Coordinates only
            </label>
          </div>
          <ul className="max-h-[360px] overflow-y-auto py-1">
            {isError && <li className="px-3 py-2 text-[12px] text-crit">Well list unavailable.</li>}
            {isLoading && <li className="px-3 py-2 font-mono text-[11px] text-faint">Loading well register…</li>}
            {data && results.length === 0 && <li className="px-3 py-2 text-[12px] text-faint">No wells match.</li>}
            {results.slice(0, 80).map((w, i) => (
              <li key={wellKey(w)}>
                <button
                  type="button"
                  data-testid={`well-search-result-${i}`}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => pick(w)}
                  className={cn("grid w-full grid-cols-[1fr_88px_120px_16px] items-center gap-2 px-3 py-1.5 text-left", i === cursor && "bg-raised", sameWell(w, currentWell) && "text-signal")}
                >
                  <span className="truncate font-mono text-[12px]">{w.well_id}</span>
                  <span className="font-mono text-[10px] text-faint">{w.dataset}</span>
                  <span className="truncate text-[11px] text-dim">{w.field_name ?? "—"}</span>
                  {!w.has_coordinates ? <MapPinOff className="size-3 text-faint" /> : <span />}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
