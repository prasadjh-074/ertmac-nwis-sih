import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useHealth } from "@/hooks/useHealth";
import { ApiError } from "@/api/client";

export interface HealthSample {
  ts: number;
  ok: boolean;
  rtt: number | null;
  serverMs: number | null;
  db: string | null;
  version: string | null;
  requestId: string | null;
  error?: string;
}

interface Telemetry {
  samples: HealthSample[];
  latest: HealthSample | null;
  refetch: () => void;
  fetching: boolean;
}

const Ctx = createContext<Telemetry | undefined>(undefined);
export const POLL_MS = 15_000;

export function AdminTelemetryProvider({ children }: { children: ReactNode }) {
  const h = useHealth(POLL_MS);
  const [samples, setSamples] = useState<HealthSample[]>([]);
  const last = useRef(0);

  useEffect(() => {
    const ts = Math.max(h.dataUpdatedAt, h.errorUpdatedAt);
    if (!ts || ts === last.current) return;
    last.current = ts;
    const isErr = h.errorUpdatedAt > h.dataUpdatedAt;
    const s: HealthSample = isErr
      ? { ts, ok: false, rtt: null, serverMs: null, db: null, version: null, requestId: h.error instanceof ApiError ? h.error.requestId : null, error: h.error instanceof Error ? h.error.message : "error" }
      : { ts, ok: h.data!.data.status === "ok", rtt: h.data!.meta.roundTripMs, serverMs: h.data!.meta.serverMs, db: h.data!.data.database, version: h.data!.data.version, requestId: h.data!.meta.requestId };
    setSamples((xs) => [...xs, s].slice(-80));
  }, [h.dataUpdatedAt, h.errorUpdatedAt, h.data, h.error]);

  return <Ctx.Provider value={{ samples, latest: samples[samples.length - 1] ?? null, refetch: () => h.refetch(), fetching: h.isFetching }}>{children}</Ctx.Provider>;
}

export function useTelemetry() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useTelemetry outside provider");
  return c;
}
