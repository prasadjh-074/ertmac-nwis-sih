// Browser-local activity record. NOT a server audit trail (backend audit endpoint pending).
export interface SessionLogEntry {
  ts: string;
  actor: string;
  action: string;
  resource: string;
  result: "Allowed" | "Denied" | "Failed";
  requestId?: string | null;
}

const KEY = "nwis-session-log";
const MAX = 300;

export function readSessionLog(): SessionLogEntry[] {
  try {
    return JSON.parse(window.localStorage.getItem(KEY) ?? "[]") as SessionLogEntry[];
  } catch {
    return [];
  }
}

export function logSessionEvent(actor: string, action: string, resource: string, result: SessionLogEntry["result"], requestId?: string | null) {
  const entry: SessionLogEntry = { ts: new Date().toISOString(), actor, action, resource, result, requestId };
  const next = [entry, ...readSessionLog()].slice(0, MAX);
  window.localStorage.setItem(KEY, JSON.stringify(next));
}

export function clearSessionLog() {
  window.localStorage.removeItem(KEY);
}
