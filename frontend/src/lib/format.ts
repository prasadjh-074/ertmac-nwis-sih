import type { WellRef } from "@/api/types";

export const wellKey = (r: WellRef) => `${r.dataset}::${r.well_id}`;
export const sameWell = (a?: WellRef | null, b?: WellRef | null) => !!a && !!b && a.dataset === b.dataset && a.well_id === b.well_id;

export const fmtNum = (v: unknown, digits = 0): string =>
  typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "—";

export const fmtDepth = (v: number | null | undefined) => (v == null ? "—" : `${fmtNum(v, 0)} m`);
export const fmtKm = (v: number | null | undefined) => (v == null ? "—" : v < 1 ? `${fmtNum(v * 1000, 0)} m` : `${fmtNum(v, 1)} km`);
export const fmtScore = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(3));
export const fmtCoord = (lat: number | null | undefined, lon: number | null | undefined) =>
  lat == null || lon == null ? "No coordinates" : `${Math.abs(lat).toFixed(4)}°${lat >= 0 ? "N" : "S"}  ${Math.abs(lon).toFixed(4)}°${lon >= 0 ? "E" : "W"}`;

export const humanize = (s: string | null | undefined) => (s ? s.replace(/_/g, " ") : "—");

export const RISK_LABELS: Record<string, string> = {
  mud_loss_risk: "Mud Loss",
  stuck_pipe_risk: "Stuck Pipe",
  kick_overpressure_risk: "Kick / Overpressure",
  torque_spike_risk: "Torque Spike",
  cementing_risk: "Cementing",
};

export const RISK_ORDER = Object.keys(RISK_LABELS);

export const riskLabel = (t: string) => RISK_LABELS[t] ?? humanize(t);

// Maps a deterministic rule to the risk category it speaks about (UI grouping only).
export function riskTypeForRule(ruleType: string): string | null {
  if (ruleType.includes("stuck_pipe")) return "stuck_pipe_risk";
  if (ruleType.includes("mud_loss")) return "mud_loss_risk";
  if (ruleType.includes("kick")) return "kick_overpressure_risk";
  if (ruleType.includes("torque")) return "torque_spike_risk";
  if (ruleType.includes("cementing")) return "cementing_risk";
  return null;
}

export const shortTime = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().replace("T", " ").slice(0, 19) + "Z";
};
