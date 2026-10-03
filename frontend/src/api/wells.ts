import { apiFetch } from "./client";
import type {
  NearbyWellListResponse,
  SimilarWellListResponse,
  WellContextResponse,
  WellListResponse,
  WellLocation,
  WellRef,
  WellStateResponse,
} from "./types";

export const listWells = (dataset?: string, limit = 500) =>
  apiFetch<WellListResponse>("/wells", { query: { dataset, limit } });

export const lookupWell = (ref: WellRef) => apiFetch<WellLocation>("/wells/lookup", { query: { ...ref } });

export const getNearbyWells = (ref: WellRef, radius_km: number, limit: number, dataset_filter?: string) =>
  apiFetch<NearbyWellListResponse>("/wells/nearby", { query: { ...ref, radius_km, limit, dataset_filter } });

export const getSimilarWells = (ref: WellRef, top_k: number, dataset_filter?: string) =>
  apiFetch<SimilarWellListResponse>("/wells/similar", { query: { ...ref, top_k, dataset_filter } });

export const getWellContext = (ref: WellRef, radius_km: number, nearby_limit = 10, similar_limit = 10) =>
  apiFetch<WellContextResponse>("/wells/context", { query: { ...ref, radius_km, nearby_limit, similar_limit } });

export const getWellState = (ref: WellRef) => apiFetch<WellStateResponse>("/wells/state", { query: { ...ref } });
