import { apiFetch } from "./client";
import type { AlertListResponse, RiskAssessResponse, WellRef } from "./types";

export interface RiskParams {
  current_depth_m?: number | null;
  current_formation?: string | null;
  radius_km?: number;
  limit?: number;
}

export const assessRisk = (ref: WellRef, p: RiskParams) =>
  apiFetch<RiskAssessResponse>("/risk/assess", { query: { ...ref, ...p } });

export const getRiskAlerts = (ref: WellRef, p: RiskParams) =>
  apiFetch<AlertListResponse>("/risk/alerts", { query: { ...ref, ...p } });
