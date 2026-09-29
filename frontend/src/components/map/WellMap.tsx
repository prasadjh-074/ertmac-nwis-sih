/**
 * Interactive well map — MapLibre GL JS, no token required.
 *
 * Basemap: OpenStreetMap's standard raster tile server
 * (tile.openstreetmap.org) — genuinely free, no key, no signup.
 * CARTO's basemaps.cartocdn.com was tried first but, as of this build,
 * silently serves a watermarked "API KEY REQUIRED" placeholder image
 * for anonymous requests instead of a real 401/403 — confirmed by
 * downloading and visually inspecting a tile (curl alone reported a
 * healthy 200 + valid PNG, which is why this needed opening the actual
 * image, not just checking the HTTP status).
 *
 * Only plots wells with real coordinates (has_coordinates === true /
 * a resolvable lat+lng). Never fabricates a position. Similar wells
 * don't carry coordinates in their own API response
 * (SimilarWellResponse has no lat/lng) so their position is resolved
 * by cross-referencing the already-fetched full well list.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type {
  NearbyWellResponse,
  SimilarWellResponse,
  WellLocationResponse,
} from "@/api/backend-types";

export interface WellMapProps {
  allWells: WellLocationResponse[];
  nearby: NearbyWellResponse[];
  similar: SimilarWellResponse[];
  current: { dataset: string; well_id: string; latitude: number | null; longitude: number | null } | null;
  onSelectWell: (dataset: string, well_id: string) => void;
  className?: string;
}

const BASEMAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: "osm-base", type: "raster", source: "osm" }],
};

function key(dataset: string, well_id: string) {
  return `${dataset}::${well_id}`;
}

function makeDot(opts: {
  size: number;
  color: string;
  border?: string;
  pulse?: boolean;
  title?: string;
}): HTMLDivElement {
  const el = document.createElement("div");
  el.title = opts.title ?? "";
  el.style.width = `${opts.size}px`;
  el.style.height = `${opts.size}px`;
  el.style.borderRadius = "9999px";
  el.style.background = opts.color;
  el.style.border = `2px solid ${opts.border ?? "#ffffff"}`;
  el.style.boxShadow = "0 1px 3px rgba(15,23,42,0.35)";
  el.style.cursor = "pointer";
  if (opts.pulse) {
    const ring = document.createElement("div");
    ring.style.position = "absolute";
    ring.style.inset = "-8px";
    ring.style.borderRadius = "9999px";
    ring.style.border = `2px solid ${opts.color}`;
    ring.style.animation = "nwis-pulse 1.8s ease-out infinite";
    el.style.position = "relative";
    el.appendChild(ring);
  }
  return el;
}

export function WellMap({ allWells, nearby, similar, current, onSelectWell, className }: WellMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [showAll, setShowAll] = useState(true);
  const [showNearby, setShowNearby] = useState(true);
  const [showSimilar, setShowSimilar] = useState(true);
  const [ready, setReady] = useState(false);
  const [tileError, setTileError] = useState<string | null>(null);

  const wellsByKey = useMemo(() => {
    const m = new Map<string, WellLocationResponse>();
    for (const w of allWells) m.set(key(w.dataset, w.well_id), w);
    return m;
  }, [allWells]);

  const resolvedSimilar = useMemo(
    () =>
      similar
        .map((s) => {
          const loc = wellsByKey.get(key(s.dataset, s.well_id));
          if (!loc || !loc.has_coordinates || loc.latitude == null || loc.longitude == null) return null;
          return { ...s, latitude: loc.latitude, longitude: loc.longitude };
        })
        .filter((s): s is SimilarWellResponse & { latitude: number; longitude: number } => s !== null),
    [similar, wellsByKey],
  );

  // Init map once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAP_STYLE,
      center: [4.0, 59.0], // roughly the Norwegian Continental Shelf
      zoom: 5,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => setReady(true));

    // Defensive: surface real tile/style load failures (network outage,
    // rate limiting, an extension blocking the request) as an honest
    // banner instead of a silently blank map. A prior version of this
    // basemap (CARTO's basemaps.cartocdn.com) turned out to serve a
    // watermarked "API key required" placeholder image on a healthy 200
    // response for anonymous requests — that image is what a user saw,
    // not a thrown error at all, which is why this handler alone can't
    // catch every bad-basemap case. The fix was switching providers
    // (see BASEMAP_STYLE); this handler still matters for genuine
    // network/permission failures against whatever provider is in use.
    map.on("error", (e) => {
      const err = e.error as { status?: number; message?: string } | undefined;
      setTileError(`Map tiles failed to load: ${err?.message ?? "unknown error"}.`);
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Redraw markers whenever data or layer toggles change.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    for (const m of markersRef.current) m.remove();
    markersRef.current = [];

    const bounds = new maplibregl.LngLatBounds();
    let hasBoundsPoint = false;

    const addMarker = (
      lng: number,
      lat: number,
      el: HTMLDivElement,
      onClick: (() => void) | null,
      extendBounds = true,
    ) => {
      const marker = new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([lng, lat]).addTo(map);
      if (onClick) el.addEventListener("click", onClick);
      markersRef.current.push(marker);
      if (extendBounds) {
        bounds.extend([lng, lat]);
        hasBoundsPoint = true;
      }
    };

    // Base layer: all wells with coordinates, muted.
    if (showAll) {
      for (const w of allWells) {
        if (!w.has_coordinates || w.latitude == null || w.longitude == null) continue;
        if (current && w.dataset === current.dataset && w.well_id === current.well_id) continue;
        const el = makeDot({ size: 8, color: "#94a3b8", title: `${w.well_id} (${w.dataset})` });
        addMarker(w.longitude, w.latitude, el, () => onSelectWell(w.dataset, w.well_id), false);
      }
    }

    // Nearby layer: sized by inverse distance.
    if (showNearby) {
      const maxDist = Math.max(1, ...nearby.map((n) => n.distance_km));
      for (const n of nearby) {
        const size = 10 + Math.round(((maxDist - n.distance_km) / maxDist) * 10);
        const el = makeDot({
          size,
          color: "#2563eb",
          title: `${n.well_id} (${n.dataset}) — ${n.distance_km.toFixed(1)} km`,
        });
        addMarker(n.longitude, n.latitude, el, () => onSelectWell(n.dataset, n.well_id));
      }
    }

    // Similar layer: colored by similarity.
    if (showSimilar) {
      for (const s of resolvedSimilar) {
        const alpha = 0.4 + Math.min(0.6, s.similarity * 0.6);
        const el = makeDot({
          size: 11,
          color: `rgba(217,119,6,${alpha.toFixed(2)})`,
          border: "#d97706",
          title: `${s.well_id} (${s.dataset}) — similarity ${s.similarity.toFixed(3)}`,
        });
        addMarker(s.longitude, s.latitude, el, () => onSelectWell(s.dataset, s.well_id));
      }
    }

    // Current well: large pulsing marker, always on top.
    if (current && current.latitude != null && current.longitude != null) {
      const el = makeDot({ size: 16, color: "#0891b2", border: "#ffffff", pulse: true, title: current.well_id });
      addMarker(current.longitude, current.latitude, el, null);
    }

    if (hasBoundsPoint) {
      map.fitBounds(bounds, { padding: 48, maxZoom: 9, duration: 600 });
    }
  }, [ready, allWells, nearby, resolvedSimilar, current, showAll, showNearby, showSimilar, onSelectWell]);

  const currentHasCoords = !!(current && current.latitude != null && current.longitude != null);

  return (
    <div className={`relative overflow-hidden border border-slate-200 ${className ?? ""}`} data-testid="well-map">
      <style>{`
        @keyframes nwis-pulse {
          0% { transform: scale(0.6); opacity: 0.9; }
          100% { transform: scale(2.4); opacity: 0; }
        }
      `}</style>
      <div ref={containerRef} className="h-full w-full" style={{ minHeight: 320 }} />

      {/* Top-anchored stack: tile-error banner (if any) above the layer toggles */}
      <div className="pointer-events-none absolute left-2 right-2 top-2 z-10 flex flex-col gap-1.5">
        {tileError && (
          <div
            className="pointer-events-auto rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[11px] text-amber-900 shadow-sm"
            data-testid="map-tile-error"
          >
            <p className="font-semibold">Basemap tiles blocked</p>
            <p className="mt-0.5 leading-relaxed">{tileError}</p>
            <p className="mt-1 text-[10px] text-amber-700">
              Well markers below are still accurate — only the background map imagery is affected.
            </p>
          </div>
        )}
        <div className="pointer-events-auto flex flex-wrap gap-1.5 self-start rounded bg-white/95 p-1.5 shadow-sm" data-testid="map-layer-toggles">
        {[
          { label: "All wells", checked: showAll, set: setShowAll, dot: "#94a3b8" },
          { label: "Nearby", checked: showNearby, set: setShowNearby, dot: "#2563eb" },
          { label: "Similar", checked: showSimilar, set: setShowSimilar, dot: "#d97706" },
        ].map((t) => (
          <button
            key={t.label}
            onClick={() => t.set((v) => !v)}
            className={`flex items-center gap-1.5 rounded border px-2 py-1 text-[10px] font-semibold transition ${
              t.checked ? "border-slate-300 bg-slate-50 text-slate-700" : "border-slate-200 bg-white text-slate-400"
            }`}
            data-testid={`map-toggle-${t.label.toLowerCase().replace(/\s+/g, "-")}`}
          >
            <span className="inline-block size-2 rounded-full" style={{ background: t.dot, opacity: t.checked ? 1 : 0.3 }} />
            {t.label}
          </button>
        ))}
        </div>
      </div>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 rounded bg-white/95 px-2.5 py-1.5 text-[10px] text-slate-600 shadow-sm">
        <div className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-full bg-cyan-600" /> Current well
        </div>
        <div className="mt-0.5 flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-full bg-blue-600" /> Nearby (size = closer)
        </div>
        <div className="mt-0.5 flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-full bg-amber-600" /> Similar (opacity = similarity)
        </div>
      </div>

      {current && !currentHasCoords && !tileError && (
        <div className="absolute inset-x-2 bottom-2 rounded border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-800">
          Current well ({current.well_id}) has no coordinates on record — not plotted.
        </div>
      )}
    </div>
  );
}
