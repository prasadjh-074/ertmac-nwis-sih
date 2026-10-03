import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { WellRef } from "@/api/types";

export interface MapPoint {
  key: string;
  well_id: string;
  dataset: string;
  lat: number;
  lon: number;
  role: "current" | "nearby" | "other";
  similar: boolean;
  highlighted: boolean;
  selected: boolean;
}

export interface LayerVisibility {
  other: boolean;
  nearby: boolean;
  similar: boolean;
}

interface WellMapProps {
  points: MapPoint[];
  fitKeys: string[];
  fitSignature: string;
  layers: LayerVisibility;
  onPick: (refs: WellRef[]) => void;
}

const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas";
const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    base: { type: "raster", tiles: [`${ESRI}/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`], tileSize: 256, maxzoom: 16, attribution: "Esri, HERE, Garmin, © OpenStreetMap contributors" },
    ref: { type: "raster", tiles: [`${ESRI}/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`], tileSize: 256, maxzoom: 16 },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#080b10" } },
    { id: "base", type: "raster", source: "base", paint: { "raster-opacity": 0.9, "raster-saturation": -0.4 } },
    { id: "ref", type: "raster", source: "ref", paint: { "raster-opacity": 0.45 } },
  ],
};

const PICKABLE = ["w-other", "w-similar", "w-nearby", "w-current"];
const SIGNAL = "#2ec5d8";

function graticule(): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  for (let lon = -4; lon <= 14; lon += 0.5) features.push({ type: "Feature", properties: { major: lon % 2 === 0 }, geometry: { type: "LineString", coordinates: [[lon, 52], [lon, 66]] } });
  for (let lat = 52; lat <= 66; lat += 0.25) features.push({ type: "Feature", properties: { major: lat % 1 === 0 }, geometry: { type: "LineString", coordinates: [[-4, lat], [14, lat]] } });
  return { type: "FeatureCollection", features };
}

function addLayers(map: maplibregl.Map) {
  map.addSource("graticule", { type: "geojson", data: graticule() });
  map.addLayer({ id: "graticule", type: "line", source: "graticule", paint: { "line-color": "#2ec5d8", "line-opacity": ["case", ["get", "major"], 0.12, 0.05], "line-width": 0.6 } });
  map.addSource("wells", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  const add = (l: maplibregl.LayerSpecification) => map.addLayer(l);
  add({ id: "w-other", type: "circle", source: "wells", filter: ["==", ["get", "role"], "other"], paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 2, 10, 4], "circle-color": "#56647a", "circle-stroke-color": "#080b10", "circle-stroke-width": 0.5 } });
  add({ id: "w-similar", type: "circle", source: "wells", filter: ["==", ["get", "similar"], true], paint: { "circle-radius": 7, "circle-color": "rgba(217,164,65,0.12)", "circle-stroke-color": "#d9a441", "circle-stroke-width": 1.5 } });
  add({ id: "w-nearby", type: "circle", source: "wells", filter: ["==", ["get", "role"], "nearby"], paint: { "circle-radius": 4.5, "circle-color": SIGNAL, "circle-stroke-color": "#080b10", "circle-stroke-width": 1 } });
  add({ id: "w-highlight", type: "circle", source: "wells", filter: ["==", ["get", "highlighted"], true], paint: { "circle-radius": 13, "circle-color": "rgba(240,244,248,0.06)", "circle-stroke-color": "#f0f4f8", "circle-stroke-width": 1.5 } });
  add({ id: "w-selected", type: "circle", source: "wells", filter: ["==", ["get", "selected"], true], paint: { "circle-radius": 18, "circle-color": "rgba(46,197,216,0.14)", "circle-stroke-color": SIGNAL, "circle-stroke-width": 1 } });
  add({ id: "w-current-ring", type: "circle", source: "wells", filter: ["==", ["get", "role"], "current"], paint: { "circle-radius": 14, "circle-color": "rgba(46,197,216,0.08)", "circle-stroke-color": SIGNAL, "circle-stroke-width": 2 } });
  add({ id: "w-current", type: "circle", source: "wells", filter: ["==", ["get", "role"], "current"], paint: { "circle-radius": 6, "circle-color": "#e6fbff", "circle-stroke-color": SIGNAL, "circle-stroke-width": 3 } });
}

function labelEl(p: MapPoint): HTMLDivElement {
  const el = document.createElement("div");
  const tone = p.role === "current" ? "#2ec5d8" : p.highlighted ? "#f0f4f8" : "#94a1b4";
  el.style.cssText = `pointer-events:none;transform:translate(14px,-50%);white-space:nowrap;font:500 10px 'IBM Plex Mono',monospace;letter-spacing:.04em;color:${tone};background:rgba(8,11,16,.82);border:1px solid ${p.role === "current" ? "rgba(46,197,216,.5)" : "#1e293b"};padding:1px 5px;`;
  el.textContent = (p.role === "current" ? "▲ " : "") + p.well_id;
  return el;
}

export function WellMap({ points, fitKeys, fitSignature, layers, onPick }: WellMapProps) {
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const labels = useRef<maplibregl.Marker[]>([]);
  const pickRef = useRef(onPick);
  const [ready, setReady] = useState(false);
  const [tileError, setTileError] = useState(false);
  pickRef.current = onPick;

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({ container: container.current, style: STYLE, center: [2.5, 59.5], zoom: 5, attributionControl: { compact: true } });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    map.on("load", () => {
      addLayers(map);
      setReady(true);
    });
    map.on("error", (e) => {
      const msg = (e.error as Error | undefined)?.message ?? "";
      if (/tile|fetch|load/i.test(msg)) setTileError(true);
    });
    map.on("click", (e) => {
      const box: [maplibregl.PointLike, maplibregl.PointLike] = [[e.point.x - 7, e.point.y - 7], [e.point.x + 7, e.point.y + 7]];
      const feats = map.queryRenderedFeatures(box, { layers: PICKABLE.filter((l) => map.getLayer(l)) });
      const seen = new Set<string>();
      const refs: WellRef[] = [];
      for (const f of feats) {
        const k = f.properties?.key as string;
        if (seen.has(k)) continue;
        seen.add(k);
        refs.push({ dataset: f.properties?.dataset as string, well_id: f.properties?.well_id as string });
      }
      if (refs.length) pickRef.current(refs);
    });
    for (const l of PICKABLE) {
      map.on("mouseenter", l, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", l, () => (map.getCanvas().style.cursor = ""));
    }
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const src = map.getSource("wells") as maplibregl.GeoJSONSource | undefined;
    src?.setData({
      type: "FeatureCollection",
      features: points.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: [p.lon, p.lat] }, properties: { ...p } })),
    });
    labels.current.forEach((m) => m.remove());
    labels.current = points
      .filter((p) => p.role === "current" || p.selected || p.highlighted)
      .slice(0, 14)
      .map((p) => new maplibregl.Marker({ element: labelEl(p), anchor: "left" }).setLngLat([p.lon, p.lat]).addTo(map));
  }, [points, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const vis = (on: boolean) => (on ? "visible" : "none");
    map.setLayoutProperty("w-other", "visibility", vis(layers.other));
    map.setLayoutProperty("w-nearby", "visibility", vis(layers.nearby));
    map.setLayoutProperty("w-similar", "visibility", vis(layers.similar));
  }, [layers, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const target = points.filter((p) => fitKeys.includes(p.key));
    if (!target.length) return;
    const b = new maplibregl.LngLatBounds();
    target.forEach((p) => b.extend([p.lon, p.lat]));
    map.fitBounds(b, { padding: { top: 80, bottom: 60, left: 60, right: 60 }, maxZoom: 11, duration: 700 });
  }, [fitSignature, ready]);

  return (
    <div className="absolute inset-0">
      <div ref={container} className="h-full w-full" data-testid="well-map-canvas" />
      {tileError && (
        <div data-testid="map-tile-error" className="absolute bottom-8 left-1/2 -translate-x-1/2 border border-warn/40 bg-warn-deep/90 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-warn">
          Basemap tiles unavailable · well positions remain accurate
        </div>
      )}
    </div>
  );
}
