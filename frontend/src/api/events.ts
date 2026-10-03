import { apiFetch } from "./client";
import type { CorrelatedEventListResponse, EventListResponse, WellRef } from "./types";

export const getWellEvents = (ref: WellRef, event_type?: string) =>
  apiFetch<EventListResponse>("/events/well", { query: { ...ref, event_type } });

export const getEventsNearDepth = (ref: WellRef, depth_m: number, tolerance_m = 100, event_type?: string) =>
  apiFetch<EventListResponse>("/events/near-depth", { query: { ...ref, depth_m, tolerance_m, event_type } });

export const getEventsByFormation = (formation: string, event_type?: string) =>
  apiFetch<EventListResponse>("/events/formation", { query: { formation, event_type } });

export interface CorrelationParams {
  current_depth_m?: number | null;
  current_formation?: string | null;
  radius_km?: number;
  limit?: number;
  event_type?: string;
}

export const getCorrelatedEvents = (ref: WellRef, p: CorrelationParams) =>
  apiFetch<CorrelatedEventListResponse>("/events/correlated", { query: { ...ref, ...p } });
