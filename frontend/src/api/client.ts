const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "/api";
const DEFAULT_TIMEOUT_MS = 90_000;

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export class ApiError extends Error {
  status: number;
  type: string;
  requestId: string | null;
  detail: unknown;

  constructor(status: number, type: string, message: string, requestId: string | null, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.type = type;
    this.requestId = requestId;
    this.detail = detail;
  }
}

export interface ApiMeta {
  requestId: string | null;
  serverMs: number | null;
  roundTripMs: number;
}

function newRequestId(): string {
  return `req_${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36).slice(-4)}`;
}

function buildUrl(path: string, query?: QueryParams): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v === undefined || v === null || v === "") continue;
    qs.set(k, String(v));
  }
  const s = qs.toString();
  return `${BASE}${path}${s ? `?${s}` : ""}`;
}

interface FetchOptions {
  method?: "GET" | "POST";
  query?: QueryParams;
  body?: unknown;
  timeoutMs?: number;
  signal?: AbortSignal;
}

export async function apiFetchWithMeta<T>(path: string, opts: FetchOptions = {}): Promise<{ data: T; meta: ApiMeta }> {
  const requestId = newRequestId();
  const controller = new AbortController();
  let timedOut = false;
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, opts.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  opts.signal?.addEventListener("abort", () => controller.abort());
  const started = performance.now();

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? "GET",
      headers: {
        Accept: "application/json",
        "X-Request-ID": requestId,
        ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    window.clearTimeout(timer);
    if (timedOut) throw new ApiError(0, "timeout", "Backend did not respond in time.", requestId);
    if (opts.signal?.aborted) throw new ApiError(0, "aborted", "Request cancelled.", requestId);
    throw new ApiError(0, "network_error", e instanceof Error ? e.message : "Network error", requestId);
  }
  window.clearTimeout(timer);

  const roundTripMs = performance.now() - started;
  const rid = res.headers.get("x-request-id") ?? requestId;
  const elapsed = res.headers.get("x-elapsed-ms");
  const meta: ApiMeta = { requestId: rid, serverMs: elapsed ? Number(elapsed) : null, roundTripMs };

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const env = body?.error;
    if (env) throw new ApiError(res.status, env.type ?? "error", env.message ?? `HTTP ${res.status}`, env.request_id ?? rid, env.detail);
    const typeFor: Record<number, string> = { 401: "unauthorized", 403: "forbidden", 404: "not_found", 502: "bad_gateway", 503: "service_unavailable", 504: "gateway_timeout" };
    throw new ApiError(res.status, typeFor[res.status] ?? "error", body?.detail ?? `HTTP ${res.status}`, rid, body);
  }
  const data = (res.status === 204 ? undefined : await res.json()) as T;
  return { data, meta };
}

export async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  return (await apiFetchWithMeta<T>(path, opts)).data;
}
