import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { useWorkspace } from "@/state/WorkspaceContext";
import { useWellState } from "@/hooks/useWellState";
import { useWellIndex } from "@/hooks/useWells";
import { fmtCoord, fmtDepth, wellKey } from "@/lib/format";
import { DataTag, Tag } from "@/components/nwis/Tags";
import { SkeletonBlock } from "@/components/nwis/States";
import { WellSearch } from "./WellSearch";

function Cell({ label, children, testid, wide }: { label: string; children: React.ReactNode; testid?: string; wide?: boolean }) {
  return (
    <div className={wide ? "min-w-[150px]" : "min-w-[84px]"}>
      <div className="label">{label}</div>
      <div data-testid={testid} className="mt-0.5 truncate font-mono text-[12px] tnum text-ink">{children}</div>
    </div>
  );
}

function DepthOverride() {
  const { depthOverride, setDepthOverride, formationOverride, setFormationOverride } = useWorkspace();
  const [d, setD] = useState(depthOverride?.toString() ?? "");
  useEffect(() => setD(depthOverride?.toString() ?? ""), [depthOverride]);
  const commit = () => {
    const n = Number(d);
    setDepthOverride(d.trim() && Number.isFinite(n) && n >= 0 ? n : null);
  };
  return (
    <div className="flex items-end gap-1.5 border-l border-line pl-4">
      <div>
        <div className="label">Assess at depth</div>
        <div className="mt-0.5 flex h-6 items-center border border-line bg-panel2 focus-within:border-signal/60">
          <input data-testid="assessment-depth-input" value={d} onChange={(e) => setD(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} placeholder="backend" inputMode="numeric" className="w-[70px] bg-transparent px-1.5 font-mono text-[12px] text-ink outline-none placeholder:text-faint" />
          <span className="pr-1.5 font-mono text-[10px] text-faint">m</span>
        </div>
      </div>
      <div>
        <div className="label">Formation</div>
        <input data-testid="assessment-formation-input" value={formationOverride} onChange={(e) => setFormationOverride(e.target.value)} placeholder="backend" className="mt-0.5 h-6 w-[96px] border border-line bg-panel2 px-1.5 font-mono text-[12px] text-ink outline-none placeholder:text-faint focus:border-signal/60" />
      </div>
      {(depthOverride != null || formationOverride) && (
        <button type="button" data-testid="assessment-reset-btn" title="Reset to backend state" onClick={() => { setDepthOverride(null); setFormationOverride(""); }} className="mb-0.5 flex size-6 items-center justify-center border border-line text-dim hover:text-ink">
          <RotateCcw className="size-3" />
        </button>
      )}
    </div>
  );
}

export function CurrentWellBar() {
  const { currentWell, depthOverride } = useWorkspace();
  const state = useWellState(currentWell);
  const index = useWellIndex();
  const loc = currentWell ? index.byKey.get(wellKey(currentWell)) : undefined;
  const s = state.data;

  return (
    <div data-testid="current-well-bar" className="flex min-h-[60px] shrink-0 items-center gap-5 border-b border-line bg-panel px-4 py-2">
      <div className="min-w-[170px] shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal">Current well</span>
          {s?.is_simulated && <DataTag kind="simulated" />}
        </div>
        {currentWell ? (
          <div className="flex items-baseline gap-2">
            <span data-testid="current-well-id" className="font-mono text-[19px] font-medium leading-tight text-ink">{currentWell.well_id}</span>
            <span className="font-mono text-[10px] text-faint">{currentWell.dataset}</span>
          </div>
        ) : (
          <span data-testid="current-well-none" className="text-[13px] text-dim">No well selected — search the register</span>
        )}
      </div>

      {currentWell && (state.isLoading ? (
        <div className="flex flex-1 gap-4">{[0, 1, 2, 3, 4].map((i) => <SkeletonBlock key={i} className="h-7 w-20" />)}</div>
      ) : state.isError ? (
        <div className="flex-1"><Tag tone="crit" testid="current-well-state-error">Well state unavailable</Tag></div>
      ) : s ? (
        <div className="flex min-w-0 flex-1 flex-wrap items-end gap-x-5 gap-y-2">
          <Cell label="Field" testid="current-well-field">{s.field_name ?? loc?.field_name ?? "—"}</Cell>
          <Cell label="Operator" wide>{s.operator ?? "—"}</Cell>
          <Cell label="Status">{s.status ?? "—"}</Cell>
          <Cell label="Hist. TD">{fmtDepth(s.total_depth_m)}</Cell>
          <Cell label={depthOverride != null ? "Depth · engineer" : "Depth · backend"} testid="current-well-depth">{fmtDepth(depthOverride ?? s.current_depth_m)}</Cell>
          <Cell label="Formation" testid="current-well-formation">{s.current_formation ?? <span className="text-faint">not resolved</span>}</Cell>
          <Cell label="Position" wide>{fmtCoord(s.latitude, s.longitude)}</Cell>
          <DepthOverride />
        </div>
      ) : null)}
      {!currentWell && <div className="flex-1" />}

      <WellSearch className="w-[280px] shrink-0" />
    </div>
  );
}
