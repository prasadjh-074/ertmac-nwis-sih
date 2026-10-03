import { useCallback, useMemo, useState } from "react";
import { Crosshair, Layers, Sparkles, X } from "lucide-react";
import type { WellRef } from "@/api/types";
import { useWellIndex } from "@/hooks/useWells";
import { useNearbyWells } from "@/hooks/useNearbyWells";
import { useSimilarWells } from "@/hooks/useSimilarWells";
import { useWorkspace } from "@/state/WorkspaceContext";
import { wellKey } from "@/lib/format";
import { cn } from "@/lib/utils";
import { WellDetailPanel } from "@/features/wells/WellDetailPanel";
import { WellMap, type LayerVisibility, type MapPoint } from "./WellMap";

const RADII = [10, 25, 50, 100, 200];

function LayerToggle({ on, onClick, swatch, label, count, testid }: { on: boolean; onClick: () => void; swatch: React.ReactNode; label: string; count?: string; testid: string }) {
  return (
    <button type="button" data-testid={testid} onClick={onClick} className={cn("flex h-7 items-center gap-2 border-r border-line px-2.5 font-mono text-[10px] uppercase tracking-[0.08em] transition-colors last:border-r-0", on ? "text-ink" : "text-faint line-through")}>
      {swatch}
      {label}
      {count && <span className="text-faint">{count}</span>}
    </button>
  );
}

export function WorkspaceMap({ className, compact = false }: { className?: string; compact?: boolean }) {
  const ws = useWorkspace();
  const { currentWell, radiusKm, setRadiusKm, selection, selectWells, highlight, setHighlight } = ws;
  const index = useWellIndex();
  const nearby = useNearbyWells(currentWell, radiusKm, 20);
  const similar = useSimilarWells(currentWell, 10);
  const [layers, setLayers] = useState<LayerVisibility>({ other: true, nearby: true, similar: true });
  const [refit, setRefit] = useState(0);

  const nearbyKeys = useMemo(() => new Set((nearby.data?.results ?? []).map(wellKey)), [nearby.data]);
  const similarKeys = useMemo(() => new Set((similar.data?.results ?? []).map(wellKey)), [similar.data]);
  const hlKeys = useMemo(() => new Set((highlight?.refs ?? []).map(wellKey)), [highlight]);
  const selKeys = useMemo(() => new Set((selection ?? []).map(wellKey)), [selection]);
  const curKey = currentWell ? wellKey(currentWell) : null;

  const points = useMemo<MapPoint[]>(() => {
    const out: MapPoint[] = [];
    for (const w of index.data?.wells ?? []) {
      if (!w.has_coordinates || w.latitude == null || w.longitude == null) continue;
      const k = wellKey(w);
      out.push({
        key: k, well_id: w.well_id, dataset: w.dataset, lat: w.latitude, lon: w.longitude,
        role: k === curKey ? "current" : nearbyKeys.has(k) ? "nearby" : "other",
        similar: similarKeys.has(k), highlighted: hlKeys.has(k), selected: selKeys.has(k),
      });
    }
    return out;
  }, [index.data, curKey, nearbyKeys, similarKeys, hlKeys, selKeys]);

  const similarUnplotted = (similar.data?.results ?? []).filter((s) => !points.some((p) => p.key === wellKey(s))).length;

  const fitKeys = useMemo(() => {
    if (highlight?.refs.length) return [...hlKeys, ...(curKey ? [curKey] : [])];
    return [...(curKey ? [curKey] : []), ...nearbyKeys];
  }, [highlight, hlKeys, curKey, nearbyKeys]);
  const fitSignature = `${fitKeys.join("|")}#${refit}#${points.length > 0}`;

  const onPick = useCallback((refs: WellRef[]) => selectWells(refs), [selectWells]);
  const toggle = (k: keyof LayerVisibility) => setLayers((l) => ({ ...l, [k]: !l[k] }));

  return (
    <div data-testid="well-map" className={cn("relative min-h-[320px] overflow-hidden border border-line bg-bg", className)}>
      <WellMap points={points} fitKeys={fitKeys} fitSignature={fitSignature} layers={layers} onPick={onPick} />

      <div className="pointer-events-none absolute inset-x-2 top-2 z-10 flex flex-wrap items-start gap-2">
        <div className="pointer-events-auto flex border border-line bg-panel/95">
          <span className="flex h-7 items-center border-r border-line px-2 text-faint"><Layers className="size-3.5" /></span>
          <LayerToggle testid="map-toggle-nearby" on={layers.nearby} onClick={() => toggle("nearby")} label="Nearby" count={nearby.data ? String(nearby.data.count) : "…"} swatch={<span className="size-2 rounded-full bg-signal" />} />
          <LayerToggle testid="map-toggle-similar" on={layers.similar} onClick={() => toggle("similar")} label="Similar" count={similar.data ? `${similar.data.count - similarUnplotted}/${similar.data.count}` : "…"} swatch={<span className="size-2.5 rounded-full border-[1.5px] border-similar" />} />
          {!compact && <LayerToggle testid="map-toggle-other" on={layers.other} onClick={() => toggle("other")} label="All wells" count={index.data ? String(index.data.count) : "…"} swatch={<span className="size-1.5 rounded-full bg-faint" />} />}
        </div>
        <div className="pointer-events-auto flex h-7 items-center border border-line bg-panel/95">
          <span className="px-2 font-mono text-[10px] uppercase tracking-[0.08em] text-faint">Radius</span>
          {RADII.map((r) => (
            <button key={r} type="button" data-testid={`map-radius-${r}`} onClick={() => setRadiusKm(r)} className={cn("h-full border-l border-line px-2 font-mono text-[10px] tnum transition-colors", r === radiusKm ? "bg-signal-deep text-signal" : "text-dim hover:text-ink")}>
              {r}
            </button>
          ))}
          <span className="border-l border-line px-2 font-mono text-[10px] text-faint">km</span>
        </div>
        <button type="button" data-testid="map-fit-btn" onClick={() => setRefit((n) => n + 1)} className="pointer-events-auto flex h-7 items-center gap-1.5 border border-line bg-panel/95 px-2.5 font-mono text-[10px] uppercase tracking-[0.08em] text-dim transition-colors hover:text-ink">
          <Crosshair className="size-3.5" /> Fit
        </button>
        {highlight && (
          <div data-testid="map-highlight-chip" className="pointer-events-auto flex h-7 items-center gap-2 border border-ink/40 bg-panel/95 pl-2.5 font-mono text-[10px] uppercase tracking-[0.08em] text-ink">
            <Sparkles className="size-3.5" /> {highlight.label} · {highlight.refs.length}
            <button type="button" data-testid="map-clear-highlight-btn" onClick={() => setHighlight(null)} className="flex h-full items-center border-l border-line px-2 text-dim hover:text-ink"><X className="size-3" /></button>
          </div>
        )}
      </div>

      <div className="pointer-events-none absolute bottom-2 left-2 z-10 flex flex-col gap-1 border border-line bg-panel/90 px-2.5 py-2 font-mono text-[10px] text-dim">
        <span className="flex items-center gap-2"><span className="size-2.5 rounded-full border-2 border-signal bg-[#e6fbff]" />Current well</span>
        <span className="flex items-center gap-2"><span className="size-2 rounded-full bg-signal" />Nearby · within {radiusKm} km</span>
        <span className="flex items-center gap-2"><span className="size-2.5 rounded-full border-[1.5px] border-similar" />Geologically similar</span>
        <span className="flex items-center gap-2"><span className="size-2.5 rounded-full border border-ink" />Highlighted</span>
        {similarUnplotted > 0 && <span className="text-faint">{similarUnplotted} similar well(s) lack coordinates · not plotted</span>}
      </div>

      {!currentWell && (
        <div className="pointer-events-none absolute inset-x-0 bottom-14 z-10 flex justify-center">
          <span className="border border-line bg-panel/95 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-dim">Select a current well to load nearby and similar wells</span>
        </div>
      )}

      {selection && selection.length > 0 && (
        <div className="absolute bottom-2 right-2 top-12 z-20 w-[340px] max-w-[calc(100%-1rem)]">
          <WellDetailPanel refs={selection} onClose={() => selectWells(null)} />
        </div>
      )}
    </div>
  );
}
