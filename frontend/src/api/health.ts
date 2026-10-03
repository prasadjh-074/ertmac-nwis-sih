import { apiFetchWithMeta } from "./client";
import type { HealthResponse } from "./types";

export const getHealth = () => apiFetchWithMeta<HealthResponse>("/health", { timeoutMs: 45_000 });
