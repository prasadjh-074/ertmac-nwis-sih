/**
 * SYSTEM_ADMIN dashboard — reads the real backend for endpoints that
 * exist (/health, /wells count, /query probe) and clearly labels
 * MOCK adapters for admin-management endpoints the backend has not
 * yet exposed. Every mock card carries a TODO(backend) placeholder
 * naming its future endpoint so it is a one-file swap when ready.
 */
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  Activity,
  Database,
  FileClock,
  Gauge,
  LockKeyhole,
  Network,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  Users,
} from "@/lib/lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AppShell } from "@/components/AppShell";
import { MockBadge, StatusBadge } from "@/components/StatusBadge";
import { useHealth, useWells } from "@/hooks/useBackend";
import { askNaturalLanguage, extractBackendError } from "@/api/backend";

// TODO(backend): swap these mock rows for real /admin/users, /admin/audit,
// /admin/ingest/status endpoints when the backend exposes them.  Every
// mock element is visibly badged so it can never be mistaken for real
// system state.
const MOCK_USERS = [
  { id: "u1", name: "Demo Engineer", email: "engineer@example.com", role: "DRILLING_ENGINEER", last_login: "2026-09-28T09:12:00Z" },
  { id: "u2", name: "Demo Admin", email: "admin@example.com", role: "SYSTEM_ADMIN", last_login: "2026-09-28T09:20:00Z" },
];

const MOCK_AUDIT = [
  { ts: "2026-09-28T09:20:00Z", actor: "admin@example.com", action: "role.switch", target: "self → SYSTEM_ADMIN", request_id: "trace-abc-001" },
  { ts: "2026-09-28T09:14:00Z", actor: "engineer@example.com", action: "risk.assess", target: "VOLVE:15/9-F-1", request_id: "trace-abc-002" },
];

const MOCK_INGEST = [
  { run_id: "run-2026-09-27", source: "SODIR wellbore_history", status: "SUCCESS", duration_s: 142, warnings: 3, errors: 0 },
  { run_id: "run-2026-09-26", source: "unified_features.parquet", status: "SUCCESS", duration_s: 87, warnings: 0, errors: 0 },
];

export default function AdminDashboard() {
  const location = useLocation();
  const health = useHealth();
  const wells = useWells({ limit: 500 });
  const section = location.pathname.split("/")[2] ?? "overview";
  const sectionTitle =
    section === "overview"
      ? "System overview"
      : section.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

  const [aiStatus, setAiStatus] = useState<"unknown" | "available" | "unavailable">("unknown");

  // AI-availability probe: POST /query with a trivial question — if
  // the backend has no GROQ_API_KEY it returns 503 with a structured
  // "service_unavailable" envelope. We only run this once on mount,
  // never on a timer, and never on the operational data path.
  useEffect(() => {
    let cancelled = false;
    askNaturalLanguage("ping")
      .then(() => {
        if (!cancelled) setAiStatus("available");
      })
      .catch((err) => {
        if (cancelled) return;
        const be = extractBackendError(err);
        setAiStatus(be?.status === 503 ? "unavailable" : "unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell>
      <div className="mx-auto max-w-[1500px] p-4 sm:p-5 lg:p-6" data-testid="admin-dashboard">
        <div className="mb-5 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                System administration
              </p>
              <StatusBadge tone="blue">
                <LockKeyhole size={11} /> Operational data restricted
              </StatusBadge>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              {sectionTitle}
            </h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-500">
              Platform health, access governance and ingestion visibility — without operational
              drilling intelligence.
            </p>
          </div>
          <Button
            variant="outline"
            className="rounded-none border-slate-300 bg-white"
            onClick={() => {
              health.refetch();
              wells.refetch();
            }}
            disabled={health.isFetching || wells.isFetching}
            data-testid="admin-refresh-health-button"
          >
            <RefreshCw
              size={15}
              className={health.isFetching || wells.isFetching ? "animate-spin" : ""}
            />{" "}
            Refresh
          </Button>
        </div>

        <div
          className="mb-5 border border-amber-200 bg-amber-50/70 px-4 py-3"
          data-testid="admin-restriction-notice"
        >
          <div className="flex items-start gap-3">
            <ShieldCheck size={18} className="mt-0.5 shrink-0 text-amber-700" />
            <div>
              <p className="text-sm font-semibold text-amber-950">
                System admin scope is intentionally separate
              </p>
              <p className="mt-1 text-xs leading-relaxed text-amber-900">
                This role does not reveal wells, drilling events, risk intelligence, confidential
                reports or the engineering assistant. Local role selection is not a production
                security boundary.
              </p>
            </div>
          </div>
        </div>

        {health.isError && (
          <div
            className="mb-4 border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800"
            data-testid="api-health-error"
          >
            /health probe failed. Start the backend with{" "}
            <code className="font-mono">uvicorn api.app:app --reload --port 8000</code>.
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
          <div className="space-y-4">
            {/* KPIs -------------------------------------------- */}
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="system-health-panel"
            >
              <CardHeader className="border-b border-slate-200 px-4 py-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Gauge size={16} className="text-blue-600" /> Platform health
                  <span className="ml-auto">
                    <StatusBadge tone={health.data?.status === "ok" ? "green" : "slate"}>
                      {health.isFetching
                        ? "Refreshing"
                        : health.data?.status === "ok"
                          ? "Operational"
                          : "Awaiting check"}
                    </StatusBadge>
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 p-4 sm:grid-cols-4">
                <div className="border border-slate-200 bg-slate-50 p-3" data-testid="api-health-metric">
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      API
                    </p>
                    <Activity
                      size={14}
                      className={health.data?.status === "ok" ? "text-emerald-600" : "text-slate-400"}
                    />
                  </div>
                  <p className="mt-2 text-sm font-bold text-slate-800">
                    {health.data?.status ?? "—"}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-slate-400">GET /health</p>
                </div>
                <div
                  className="border border-slate-200 bg-slate-50 p-3"
                  data-testid="database-health-metric"
                >
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Database
                  </p>
                  <p className="mt-2 text-sm font-bold text-slate-800">
                    {health.data?.database ?? "—"}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-slate-400">/health.database</p>
                </div>
                <div
                  className="border border-slate-200 bg-slate-50 p-3"
                  data-testid="wells-count-metric"
                >
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Wells indexed
                  </p>
                  <p className="mt-2 font-mono text-lg font-bold text-slate-800">
                    {wells.data?.count ?? "—"}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-slate-400">GET /wells</p>
                </div>
                <div className="border border-slate-200 bg-slate-50 p-3" data-testid="ai-availability-metric">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    AI (Groq /query)
                  </p>
                  <p className="mt-2 text-sm font-bold text-slate-800">
                    {aiStatus === "unknown"
                      ? "Checking…"
                      : aiStatus === "available"
                        ? "Available"
                        : "Unavailable"}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-slate-400">POST /query</p>
                </div>
              </CardContent>
            </Card>

            {/* Users & roles (mock) --------------------------- */}
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="users-roles-panel"
            >
              <CardHeader className="border-b border-slate-200 px-4 py-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Users size={16} className="text-blue-600" /> Users & roles
                  <MockBadge future />
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-left text-xs" data-testid="admin-users-table">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
                      <th className="px-4 py-2 font-bold">Name</th>
                      <th className="px-4 py-2 font-bold">Email</th>
                      <th className="px-4 py-2 font-bold">Role</th>
                      <th className="px-4 py-2 font-bold">Last login</th>
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_USERS.map((u) => (
                      <tr key={u.id} className="border-b border-slate-100">
                        <td className="px-4 py-2 font-semibold text-slate-800">{u.name}</td>
                        <td className="px-4 py-2 font-mono text-[11px] text-slate-600">
                          {u.email}
                        </td>
                        <td className="px-4 py-2">
                          <StatusBadge tone={u.role === "SYSTEM_ADMIN" ? "amber" : "blue"}>
                            {u.role}
                          </StatusBadge>
                        </td>
                        <td className="px-4 py-2 font-mono text-[11px] text-slate-500">
                          {u.last_login.slice(0, 19).replace("T", " ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">
                  Mock adapter — TODO(backend): swap for GET /admin/users, PATCH /admin/users/{"{id}"}.
                </p>
              </CardContent>
            </Card>

            {/* Access policy (UX) ----------------------------- */}
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="access-policies-panel"
            >
              <CardHeader className="border-b border-slate-200 px-4 py-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <ShieldCheck size={16} className="text-blue-600" /> Access policy model{" "}
                  <StatusBadge tone="blue">UX policy</StatusBadge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="overflow-x-auto">
                  <table
                    className="w-full min-w-[460px] text-left text-xs"
                    data-testid="access-policy-table"
                  >
                    <thead>
                      <tr className="border-b border-slate-200 text-[10px] uppercase tracking-wider text-slate-500">
                        <th className="pb-3 font-bold">Role</th>
                        <th className="pb-3 font-bold">Operational data</th>
                        <th className="pb-3 font-bold">System data</th>
                        <th className="pb-3 font-bold">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-slate-100">
                        <td className="py-3 font-semibold text-slate-800">DRILLING_ENGINEER</td>
                        <td className="py-3 text-emerald-700">Allowed</td>
                        <td className="py-3 text-slate-500">Restricted</td>
                        <td className="py-3">
                          <StatusBadge tone="slate">App policy</StatusBadge>
                        </td>
                      </tr>
                      <tr>
                        <td className="py-3 font-semibold text-slate-800">SYSTEM_ADMIN</td>
                        <td className="py-3 text-amber-700">Restricted</td>
                        <td className="py-3 text-emerald-700">Allowed</td>
                        <td className="py-3">
                          <StatusBadge tone="slate">App policy</StatusBadge>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  Frontend role rules from the product brief. Backend auth is not yet enforced —
                  swap the RoleContext for a real JWT/OAuth exchange when server-side identity is
                  wired.
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-4">
            {/* Ingestion pipeline (mock) --------------------- */}
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="admin-ingestion-panel"
            >
              <CardHeader className="border-b border-slate-200 px-4 py-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Network size={16} className="text-blue-600" /> Ingestion pipeline{" "}
                  <MockBadge future />
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-3">
                {MOCK_INGEST.map((r) => (
                  <div key={r.run_id} className="border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between">
                      <p className="font-mono text-xs font-semibold text-slate-800">{r.run_id}</p>
                      <StatusBadge tone={r.errors === 0 ? "green" : "red"}>{r.status}</StatusBadge>
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500">{r.source}</p>
                    <p className="mt-1 font-mono text-[10px] text-slate-500">
                      {r.duration_s}s · warnings {r.warnings} · errors {r.errors}
                    </p>
                  </div>
                ))}
                <p className="px-1 pt-1 text-[11px] text-slate-500">
                  TODO(backend): GET /admin/ingest/runs
                </p>
              </CardContent>
            </Card>

            {/* Audit log (mock) ------------------------------ */}
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="recent-activity-panel"
            >
              <CardHeader className="border-b border-slate-200 px-4 py-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <FileClock size={16} className="text-blue-600" /> Recent activity{" "}
                  <MockBadge future />
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <ul className="divide-y divide-slate-100" data-testid="admin-audit-list">
                  {MOCK_AUDIT.map((row, i) => (
                    <li key={i} className="p-3 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono font-semibold text-slate-800">
                          {row.action}
                        </span>
                        <span className="font-mono text-[10px] text-slate-500">
                          {row.ts.slice(0, 19).replace("T", " ")}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-500">
                        <span className="font-semibold text-slate-700">{row.actor}</span> →{" "}
                        {row.target}
                      </p>
                      <p className="mt-1 font-mono text-[10px] text-slate-400">
                        req: {row.request_id}
                      </p>
                    </li>
                  ))}
                </ul>
                <p className="border-t border-slate-100 px-3 py-2 text-[11px] text-slate-500">
                  TODO(backend): GET /admin/audit
                </p>
              </CardContent>
            </Card>

            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="admin-capability-grid"
            >
              <CardHeader className="border-b border-slate-200 px-4 py-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <ServerCog size={16} className="text-blue-600" /> Administration capabilities
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-3">
                <div className="border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center gap-2">
                    <Database size={15} className="text-slate-500" />
                    <p className="text-sm font-semibold text-slate-800">Database health</p>
                    <span className="ml-auto">
                      <StatusBadge tone="green">Live</StatusBadge>
                    </span>
                  </div>
                  <p className="mt-2 font-mono text-[11px] text-slate-600">
                    /health.database = {health.data?.database ?? "—"}
                  </p>
                </div>
                <div className="border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center gap-2">
                    <Network size={15} className="text-slate-500" />
                    <p className="text-sm font-semibold text-slate-800">Ingestion pipeline</p>
                    <span className="ml-auto">
                      <MockBadge future />
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Pipeline state and source freshness — pending backend endpoint.
                  </p>
                </div>
                <div className="border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center gap-2">
                    <FileClock size={15} className="text-slate-500" />
                    <p className="text-sm font-semibold text-slate-800">Audit log</p>
                    <span className="ml-auto">
                      <MockBadge future />
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Audit records will render only when the backend returns them.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card
              className="rounded-none border-slate-200 bg-[#0f172a] text-white shadow-sm"
              data-testid="admin-principle-card"
            >
              <CardContent className="p-5">
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-300">
                  Governance principle
                </p>
                <p className="mt-3 text-lg font-semibold leading-snug">
                  System administration is not operational intelligence.
                </p>
                <p className="mt-2 text-xs leading-relaxed text-slate-400">
                  Role separation remains visible even while backend system-management endpoints
                  are pending.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
