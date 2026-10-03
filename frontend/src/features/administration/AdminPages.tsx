import { useMemo, useState } from "react";
import { ArrowRight, RefreshCw, Trash2 } from "lucide-react";
import { clearSessionLog, readSessionLog } from "@/lib/sessionLog";
import { fmtNum, shortTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { KV, Panel, ToolButton } from "@/components/nwis/Panel";
import { DataTag, StatusDot, Tag } from "@/components/nwis/Tags";
import { EmptyState } from "@/components/nwis/States";
import { POLL_MS, useTelemetry } from "./AdminTelemetry";
import { apiState, dbState, LatencyChart, StatusTile } from "./AdminOverview";

const STAGES = [
  { name: "SODIR knowledge layer", detail: "core / subsurface schemas · wellbore history" },
  { name: "FORCE 2020", detail: "well-log dataset · 30-dim well/window embeddings" },
  { name: "VOLVE", detail: "well-log dataset · 30-dim well/window embeddings" },
  { name: "Document ingestion", detail: "PDF · text · scanned images" },
  { name: "OCR", detail: "Tesseract · PyMuPDF text extraction" },
  { name: "Handwriting detection", detail: "page classification: typed / handwritten / mixed" },
  { name: "Entity & relation extraction", detail: "deterministic rules · reference-table resolution" },
  { name: "Embedding pipeline", detail: "all-MiniLM-L6-v2 · 384-dim chunks in pgvector" },
];

export function IngestionPipeline() {
  return (
    <div data-testid="admin-ingestion" className="flex min-h-full flex-col gap-1.5 p-1.5">
      <Panel code="I-01" title="Data ingestion pipeline" meta="stage catalogue from repository docs" testid="ingestion-panel" actions={<DataTag kind="pending" />}>
        <ol className="divide-y divide-line-soft">
          {STAGES.map((s, i) => (
            <li key={s.name} data-testid={`ingestion-stage-${i}`} className="grid grid-cols-[40px_minmax(0,1fr)_200px] items-center gap-3 px-3 py-2.5">
              <span className="font-mono text-[11px] text-faint">{String(i + 1).padStart(2, "0")}</span>
              <div><div className="text-[13px]">{s.name}</div><div className="font-mono text-[10px] text-faint">{s.detail}</div></div>
              <div className="flex items-center justify-end gap-2 font-mono text-[10px] uppercase text-faint"><StatusDot state="unknown" />status not reported</div>
            </li>
          ))}
        </ol>
        <p className="px-3 py-2 font-mono text-[10px] text-faint">The backend exposes no ingestion status API. Stage health is shown as unknown rather than assumed healthy.</p>
      </Panel>
      <div className="flex flex-wrap items-center gap-2 border border-line bg-panel px-3 py-2.5 font-mono text-[10px] uppercase text-dim">
        {["Sources", "OCR + handwriting", "Extraction", "Resolution", "Chunk + embed", "PostgreSQL / pgvector"].map((s, i, a) => (
          <span key={s} className="flex items-center gap-2">{s}{i < a.length - 1 && <ArrowRight className="size-3 text-faint" />}</span>
        ))}
      </div>
    </div>
  );
}

export function SystemHealth() {
  const { latest, samples, refetch, fetching } = useTelemetry();
  const ok = samples.filter((s) => s.ok).length;
  return (
    <div data-testid="admin-health" className="flex min-h-full flex-col gap-1.5 p-1.5">
      <div className="grid grid-cols-2 gap-1.5 lg:grid-cols-4">
        <StatusTile testid="health-api" label="API" state={apiState(latest)} value={!latest ? "checking" : latest.ok ? "healthy" : "unreachable"} sub={latest?.error ?? "status: ok"} />
        <StatusTile testid="health-version" label="Version" state={latest?.version ? "ok" : "unknown"} value={latest?.version ?? "—"} sub="from /health" />
        <StatusTile testid="health-rtt" label="Response time" state={latest?.rtt == null ? "unknown" : latest.rtt > 3000 ? "warn" : "ok"} value={latest?.rtt != null ? `${fmtNum(latest.rtt, 0)} ms` : "—"} sub={`server ${fmtNum(latest?.serverMs, 1)} ms · X-Elapsed-Ms`} />
        <StatusTile testid="health-availability" label="Session availability" state={!samples.length ? "unknown" : ok === samples.length ? "ok" : "warn"} value={samples.length ? `${fmtNum((ok / samples.length) * 100, 1)}%` : "—"} sub={`${ok}/${samples.length} checks ok`} />
      </div>
      <Panel code="H-01" title="Latency history" meta={`polled every ${POLL_MS / 1000} s · client-measured`} testid="health-latency-panel" className="min-h-[300px] flex-1" actions={<ToolButton testid="health-check-now-btn" onClick={refetch}><RefreshCw className={cn("size-3", fetching && "animate-spin")} />Check now</ToolButton>}>
        <LatencyChart samples={samples} />
      </Panel>
      <div className="font-mono text-[10px] text-faint">last request id {latest?.requestId ?? "—"}</div>
    </div>
  );
}

export function DatabaseHealth() {
  const { latest, samples } = useTelemetry();
  const connected = samples.filter((s) => s.db === "connected").length;
  return (
    <div data-testid="admin-database" className="flex min-h-full flex-col gap-1.5 p-1.5">
      <div className="grid grid-cols-2 gap-1.5 lg:grid-cols-3">
        <StatusTile testid="db-status" label="PostgreSQL" state={dbState(latest)} value={latest?.db ?? "checking"} sub="SELECT 1 probe via /health" />
        <StatusTile testid="db-connected-ratio" label="Connected checks" state={samples.length ? "ok" : "unknown"} value={samples.length ? `${connected}/${samples.length}` : "—"} sub="this session" />
        <StatusTile testid="db-pool" label="Pool / vector index stats" state="unknown" value="not reported" pending />
      </div>
      <Panel code="D-01" title="Probe log" testid="db-probe-panel" className="flex-1">
        {!samples.length ? <EmptyState title="Waiting for first probe" /> : (
          <ul className="divide-y divide-line-soft">
            {[...samples].reverse().slice(0, 40).map((s) => (
              <li key={s.ts} className="grid grid-cols-[180px_120px_100px_1fr] gap-3 px-3 py-1.5 font-mono text-[11px]">
                <span className="text-faint">{shortTime(new Date(s.ts).toISOString())}</span>
                <span className={s.db === "connected" ? "text-ok" : "text-crit"}>{s.db ?? "no response"}</span>
                <span className="text-dim">{fmtNum(s.rtt, 0)} ms</span>
                <span className="truncate text-faint">{s.requestId}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

export function AuditLogs() {
  const [, setTick] = useState(0);
  const [result, setResult] = useState<string>("all");
  const log = readSessionLog();
  const rows = useMemo(() => log.filter((e) => result === "all" || e.result === result), [log, result]);
  return (
    <div data-testid="admin-audit" className="flex min-h-full flex-col gap-1.5 p-1.5">
      <div className="flex flex-wrap items-center gap-2 border border-dashed border-warn/40 bg-warn-deep/30 px-3 py-2">
        <DataTag kind="local" />
        <span className="text-[12px] text-dim">Recorded by this browser during demo sessions. Not a server audit trail · backend audit endpoint pending.</span>
      </div>
      <Panel code="L-01" title="Audit log" meta={`${rows.length} entries`} testid="audit-panel" className="flex-1"
        actions={<>
          {["all", "Allowed", "Denied", "Failed"].map((r) => <ToolButton key={r} testid={`audit-filter-${r}`} active={result === r} onClick={() => setResult(r)}>{r}</ToolButton>)}
          <ToolButton testid="audit-clear-btn" onClick={() => { clearSessionLog(); setTick((t) => t + 1); }}><Trash2 className="size-3" />Clear</ToolButton>
        </>}>
        {!rows.length ? <EmptyState title="No entries" /> : (
          <table className="w-full text-left text-[12px]" data-testid="audit-table">
            <thead className="sticky top-0 bg-panel font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
              <tr className="border-b border-line"><th className="px-3 py-1.5">Timestamp</th><th>Actor</th><th>Action</th><th>Resource</th><th>Result</th><th>Request ID</th></tr>
            </thead>
            <tbody className="divide-y divide-line-soft font-mono text-[11px]">
              {rows.map((e, i) => (
                <tr key={i}>
                  <td className="px-3 py-1.5 text-faint">{shortTime(e.ts)}</td><td>{e.actor}</td><td className="font-sans text-[12px]">{e.action}</td><td className="text-dim">{e.resource}</td>
                  <td><Tag tone={e.result === "Allowed" ? "ok" : e.result === "Denied" ? "crit" : "warn"}>{e.result}</Tag></td><td className="text-faint">{e.requestId ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

export function SecurityPosture() {
  const items = [
    { k: "Authentication", v: "Demo role picker (localStorage)", tone: "warn" as const, next: "Organizational SSO · OIDC / OAuth2" },
    { k: "Identity token", v: "None issued", tone: "warn" as const, next: "Signed JWT with role claims" },
    { k: "Backend authorization", v: "Not enforced by API", tone: "crit" as const, next: "FastAPI dependency validating token + permission per route" },
    { k: "Data-level access", v: "No per-well / per-document ACL", tone: "crit" as const, next: "Scope filters applied in resolver & SQL layer" },
    { k: "Frontend route guards", v: "Permission-based (RequirePermission)", tone: "ok" as const, next: "Kept as UX layer only" },
    { k: "Request tracing", v: "X-Request-ID sent and preserved", tone: "ok" as const, next: "Correlate with server audit log" },
  ];
  return (
    <div data-testid="admin-security" className="flex min-h-full flex-col gap-1.5 p-1.5">
      <Panel code="X-01" title="Security posture" meta="honest current state" testid="security-panel">
        <div className="divide-y divide-line-soft">
          {items.map((i) => (
            <div key={i.k} className="grid grid-cols-[200px_minmax(0,1fr)_minmax(0,1fr)] items-center gap-4 px-3 py-2.5">
              <span className="text-[13px]">{i.k}</span>
              <Tag tone={i.tone} className="w-fit">{i.v}</Tag>
              <span className="text-[12px] text-dim"><span className="label mr-2">target</span>{i.next}</span>
            </div>
          ))}
        </div>
      </Panel>
      <Panel code="X-02" title="Target authorization chain" testid="security-chain-panel">
        <div className="flex flex-wrap items-center gap-2 p-3 font-mono text-[11px] uppercase text-dim">
          {["Login", "Identity", "Role", "Permissions", "Backend authorization", "Data access"].map((s, i, a) => (
            <span key={s} className="flex items-center gap-2"><span className={cn("border px-2 py-1", i >= 4 ? "border-dashed border-warn/50 text-warn" : "border-line")}>{s}</span>{i < a.length - 1 && <ArrowRight className="size-3 text-faint" />}</span>
          ))}
        </div>
        <p className="px-3 pb-3 text-[12px] text-dim">Dashed stages do not exist yet. Until they do, hiding navigation in the UI is a convenience, not a security boundary.</p>
      </Panel>
      <div className="grid grid-cols-3 gap-4 border border-line bg-panel p-3"><KV label="Auth mode" value="DEMO" /><KV label="Session storage" value="localStorage" /><KV label="Logout clears" value="query cache + session" /></div>
    </div>
  );
}
