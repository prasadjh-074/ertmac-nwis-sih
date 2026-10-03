import { Link } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RefreshCw } from "lucide-react";
import { readSessionLog } from "@/lib/sessionLog";
import { fmtNum, shortTime } from "@/lib/format";
import { Panel, ToolButton } from "@/components/nwis/Panel";
import { DataTag, StatusDot, Tag } from "@/components/nwis/Tags";
import { EmptyState, SkeletonBlock } from "@/components/nwis/States";
import { POLL_MS, useTelemetry, type HealthSample } from "./AdminTelemetry";

export function StatusTile({ label, state, value, sub, testid, pending }: { label: string; state: "ok" | "warn" | "crit" | "unknown"; value: string; sub?: string; testid: string; pending?: boolean }) {
  return (
    <div data-testid={testid} className="border border-line bg-panel px-4 py-3">
      <div className="label">{label}</div>
      <div className="mt-2 flex items-center gap-2"><StatusDot state={state} /><span className="font-mono text-[15px] uppercase tracking-[0.04em]">{value}</span></div>
      {sub && <div className="mt-1 font-mono text-[10px] text-faint">{sub}</div>}
      {pending && <DataTag kind="pending" className="mt-2" />}
    </div>
  );
}

export function apiState(s: HealthSample | null) {
  return !s ? "unknown" : !s.ok ? "crit" : "ok";
}
export function dbState(s: HealthSample | null) {
  return !s ? "unknown" : !s.ok ? "unknown" : s.db === "connected" ? "ok" : "crit";
}

export function LatencyChart({ samples }: { samples: HealthSample[] }) {
  if (!samples.length) return <SkeletonBlock className="m-3 h-[200px]" />;
  const data = samples.map((s) => ({ t: new Date(s.ts).toISOString().slice(11, 19), rtt: s.rtt != null ? Math.round(s.rtt) : null, server: s.serverMs != null ? Number(s.serverMs.toFixed(1)) : null }));
  return (
    <div className="h-full min-h-[200px] p-2" data-testid="latency-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="2 4" />
          <XAxis dataKey="t" stroke="#5b687b" tick={{ fontSize: 9, fontFamily: "IBM Plex Mono" }} minTickGap={40} />
          <YAxis stroke="#5b687b" tick={{ fontSize: 9, fontFamily: "IBM Plex Mono" }} unit=" ms" width={60} />
          <Tooltip contentStyle={{ background: "#0d1219", border: "1px solid #1e293b", fontFamily: "IBM Plex Mono", fontSize: 11 }} />
          <Line type="stepAfter" dataKey="rtt" name="round-trip" stroke="#2ec5d8" dot={false} strokeWidth={1.5} connectNulls={false} isAnimationActive={false} />
          <Line type="stepAfter" dataKey="server" name="server processing" stroke="#f0a63a" dot={false} strokeWidth={1.5} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const METRICS = ["Users", "Active sessions", "Documents", "Indexed wells"];

export function AdminOverview() {
  const { latest, samples, refetch, fetching } = useTelemetry();
  const log = readSessionLog().slice(0, 8);
  return (
    <div data-testid="admin-overview" className="flex min-h-full flex-col gap-1.5 p-1.5">
      <div className="flex items-center gap-3 border border-line bg-panel px-4 py-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-warn">System administration</div>
          <div className="mt-0.5 text-[13px] text-dim">Operational drilling intelligence is restricted for this role.</div>
        </div>
        <ToolButton testid="admin-refresh-health-btn" className="ml-auto" onClick={refetch}><RefreshCw className={fetching ? "size-3 animate-spin" : "size-3"} />Check now</ToolButton>
      </div>
      <div className="grid grid-cols-2 gap-1.5 lg:grid-cols-4">
        <StatusTile testid="status-api" label="API" state={apiState(latest)} value={!latest ? "checking" : latest.ok ? "healthy" : "unreachable"} sub={latest?.version ? `v${latest.version} · GET /health` : "GET /health"} />
        <StatusTile testid="status-database" label="Database" state={dbState(latest)} value={latest?.db ?? (latest ? "unknown" : "checking")} sub="reported by /health" />
        <StatusTile testid="status-vector" label="Vector search" state="unknown" value="not reported" sub="no status endpoint" pending />
        <StatusTile testid="status-ingestion" label="Ingestion" state="unknown" value="not reported" sub="no status endpoint" pending />
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-1.5 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel code="S-01" title="API latency · this session" meta={`${samples.length} samples · every ${POLL_MS / 1000}s`} testid="admin-latency-panel" className="min-h-[260px]"><LatencyChart samples={samples} /></Panel>
        <Panel code="S-02" title="Platform metrics" testid="admin-metrics-panel" actions={<DataTag kind="mock" />}>
          <div className="divide-y divide-line-soft">
            {METRICS.map((m) => (
              <div key={m} className="flex items-center justify-between px-3 py-2.5">
                <span className="text-[12px] text-dim">{m}</span>
                <span className="font-mono text-[13px] text-faint" data-testid={`metric-${m.toLowerCase().replace(/ /g, "-")}`}>— <span className="text-[10px]">no admin metrics API</span></span>
              </div>
            ))}
          </div>
          <p className="px-3 py-2 font-mono text-[10px] text-faint">Values are withheld rather than estimated. Admin roles do not query operational endpoints to derive counts.</p>
        </Panel>
      </div>
      <Panel code="S-03" title="Recent activity" meta="this browser only" testid="admin-activity-panel" actions={<><DataTag kind="local" /><Link to="/admin/audit" className="font-mono text-[10px] uppercase text-signal hover:underline">Audit log</Link></>}>
        {!log.length ? <EmptyState title="No activity recorded" /> : (
          <ul className="divide-y divide-line-soft">
            {log.map((e, i) => (
              <li key={i} className="grid grid-cols-[170px_110px_1fr_80px] gap-3 px-3 py-1.5 font-mono text-[11px]">
                <span className="text-faint">{shortTime(e.ts)}</span><span>{e.actor}</span><span className="truncate text-dim">{e.action} · {e.resource}</span>
                <Tag tone={e.result === "Allowed" ? "ok" : e.result === "Denied" ? "crit" : "warn"}>{e.result}</Tag>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <p className="px-1 font-mono text-[10px] text-faint">Latest round-trip {fmtNum(latest?.rtt, 0)} ms · server {fmtNum(latest?.serverMs, 1)} ms</p>
    </div>
  );
}
