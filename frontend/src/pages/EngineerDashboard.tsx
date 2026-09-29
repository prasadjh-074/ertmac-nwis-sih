/**
 * DRILLING_ENGINEER dashboard — consumes the real FastAPI backend
 * (see docs/backend_api.md).  Every panel here is a thin view over
 * a TanStack Query hook in src/hooks/useBackend.ts; nothing is
 * fabricated when data is missing — empty states are labelled.
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  CircleAlert,
  FileSearch,
  MapPinned,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
  TableProperties,
  Waves,
} from "@/lib/lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AppShell } from "@/components/AppShell";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { WellMap } from "@/components/map/WellMap";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/auth/AuthContext";
import {
  useAskNaturalLanguage,
  useAskStructured,
  useCorrelatedEvents,
  useDocumentSearch,
  useEventsForWell,
  useHealth,
  useNearbyWells,
  useRiskAlerts,
  useRiskAssess,
  useSimilarWells,
  useWellState,
  useWells,
} from "@/hooks/useBackend";
import { extractBackendError } from "@/api/backend";
import type {
  Alert,
  DocumentChunk,
  RiskAssessment,
} from "@/api/backend-types";

// ── Shared micro-components ──────────────────────────────────
function SectionKicker({ children }: { children: string }) {
  return (
    <p
      className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500"
      data-testid={`section-kicker-${children.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
    >
      {children}
    </p>
  );
}

function PanelHeader({
  icon: Icon,
  title,
  detail,
  action,
}: {
  icon: typeof Activity;
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 text-blue-600">
          <Icon size={17} />
        </div>
        <div>
          <h2
            className="text-sm font-bold text-slate-900"
            data-testid={`panel-title-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
          >
            {title}
          </h2>
          {detail && <p className="mt-0.5 text-xs text-slate-500">{detail}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

function ErrorLine({ err }: { err: unknown }) {
  const be = extractBackendError(err);
  if (!be) {
    return (
      <p className="text-xs text-red-700" data-testid="error-line">
        Request failed. Check the backend is running on http://127.0.0.1:8000.
      </p>
    );
  }
  return (
    <p className="text-xs text-red-700" data-testid="error-line">
      {be.message}{" "}
      {be.requestId && (
        <span className="font-mono text-[10px] text-red-500">req: {be.requestId.slice(0, 8)}</span>
      )}
    </p>
  );
}

function Skel({ h = 24 }: { h?: number }) {
  return <div className="animate-pulse bg-slate-100" style={{ height: h }} />;
}

function LevelBadge({ level }: { level: string }) {
  const l = level.toLowerCase();
  const tone: "red" | "amber" | "blue" | "slate" =
    l === "high" || l === "critical"
      ? "red"
      : l === "medium" || l === "warning"
        ? "amber"
        : l === "low" || l === "info"
          ? "blue"
          : "slate";
  return <StatusBadge tone={tone}>{level.toUpperCase()}</StatusBadge>;
}

// ── Component ────────────────────────────────────────────────
export default function EngineerDashboard() {
  const { user } = useAuth();
  const location = useLocation();
  const section = location.pathname.split("/")[2] ?? "overview";

  // Sidebar links change the URL; scroll to the panel that section names.
  useEffect(() => {
    const panelByPath: Record<string, string> = {
      wells: "well-intelligence-map-panel",
      risk: "risk-alert-station",
      events: "events-panel",
      documents: "document-vault-panel",
    };
    const testId = panelByPath[section];
    const frame = requestAnimationFrame(() => {
      const el = testId ? document.querySelector(`[data-testid="${testId}"]`) : null;
      if (!el) {
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }
      // 68px sticky header + a little breathing room
      const top = el.getBoundingClientRect().top + window.scrollY - 84;
      window.scrollTo({ top, behavior: "smooth" });
    });
    return () => cancelAnimationFrame(frame);
  }, [section]);

  const health = useHealth();
  const wellsQuery = useWells({ limit: 200 });

  // Current-well selection (persist to localStorage so a navigation
  // between sub-routes doesn't lose it).
  const [selection, setSelection] = useState<{ dataset: string; well_id: string } | null>(() => {
    try {
      const raw = localStorage.getItem("nwis.currentWell");
      return raw ? (JSON.parse(raw) as { dataset: string; well_id: string }) : null;
    } catch {
      return null;
    }
  });
  const selectWell = (dataset: string, well_id: string) => {
    setSelection({ dataset, well_id });
    try {
      localStorage.setItem("nwis.currentWell", JSON.stringify({ dataset, well_id }));
    } catch {
      /* noop */
    }
  };

  const wellState = useWellState(selection?.dataset ?? null, selection?.well_id ?? null);
  const nearby = useNearbyWells(selection?.dataset ?? null, selection?.well_id ?? null, 50, 10);
  const similar = useSimilarWells(selection?.dataset ?? null, selection?.well_id ?? null, 10);
  const events = useEventsForWell(selection?.dataset ?? null, selection?.well_id ?? null);
  const correlated = useCorrelatedEvents(
    selection?.dataset ?? null,
    selection?.well_id ?? null,
    wellState.data?.current_depth_m ?? undefined,
    wellState.data?.current_formation ?? undefined,
    50,
    20,
  );
  const riskAssess = useRiskAssess(
    selection?.dataset ?? null,
    selection?.well_id ?? null,
    wellState.data?.current_depth_m ?? undefined,
    wellState.data?.current_formation ?? undefined,
  );
  const riskAlerts = useRiskAlerts(
    selection?.dataset ?? null,
    selection?.well_id ?? null,
    wellState.data?.current_depth_m ?? undefined,
    wellState.data?.current_formation ?? undefined,
  );

  const [wellSearch, setWellSearch] = useState("");
  const filteredWells = useMemo(() => {
    const q = wellSearch.trim().toLowerCase();
    const list = wellsQuery.data?.wells ?? [];
    if (!q) return list.slice(0, 30);
    return list
      .filter(
        (w) =>
          w.well_id.toLowerCase().includes(q) ||
          (w.field_name ?? "").toLowerCase().includes(q) ||
          w.dataset.toLowerCase().includes(q),
      )
      .slice(0, 30);
  }, [wellsQuery.data, wellSearch]);

  // AI / Query panel state
  const [queryText, setQueryText] = useState("");
  const [lastAnswerSource, setLastAnswerSource] = useState<"nl" | "structured" | null>(null);
  const nlAsk = useAskNaturalLanguage();
  const structuredAsk = useAskStructured();
  const answerData = lastAnswerSource === "structured" ? structuredAsk.data : nlAsk.data;
  const answerError = lastAnswerSource === "structured" ? structuredAsk.error : nlAsk.error;
  const answerPending = nlAsk.isPending || structuredAsk.isPending;

  // Without this, asking about well A then switching to well B leaves
  // well A's answer visible under the new well context — not wrong
  // data (the answer text still names well A), but stale and easy to
  // misread as being about the newly selected well. Clear on well change.
  useEffect(() => {
    setLastAnswerSource(null);
    setQueryText("");
    nlAsk.reset();
    structuredAsk.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection?.dataset, selection?.well_id]);

  // The Groq interpreter has no notion of "current well" — it only
  // sees the raw question text. Left ungrounded, a question like
  // "what happened nearby?" makes the LLM guess target_well_id, which
  // then fails resolution. Verified live against the backend: naming
  // the well explicitly in the question text fixes resolution, so we
  // inject that context invisibly rather than asking the user to type
  // well IDs into every question.
  const wellContextPrefix = useMemo(() => {
    if (!selection) return "";
    const bits = [`well ${selection.well_id} in dataset ${selection.dataset}`];
    if (wellState.data?.current_depth_m != null) {
      bits.push(`at depth ${wellState.data.current_depth_m.toFixed(0)} m`);
    }
    if (wellState.data?.current_formation) {
      bits.push(`in the ${wellState.data.current_formation} formation`);
    }
    return `Regarding ${bits.join(" ")}: `;
  }, [selection, wellState.data]);

  // A 200 response can still be a non-answer — the resolver failed
  // silently (target_well_id came back "UNKNOWN") or the graph
  // reported node errors. Treat both as failures so the panel never
  // presents an empty/wrong answer as if it were real.
  const isHollowAnswer = (data: typeof nlAsk.data) =>
    !data ||
    (data.errors && data.errors.length > 0) ||
    (data.structured_query as { target_well_id?: string } | null)?.target_well_id === "UNKNOWN";

  const runStructuredFallback = () => {
    if (!selection) return;
    setLastAnswerSource("structured");
    structuredAsk.mutate({
      intent: "similar_wells",
      target_dataset: selection.dataset,
      target_well_id: selection.well_id,
      top_k: 5,
    });
  };

  const submitQuestion = () => {
    if (!queryText.trim()) return;
    setLastAnswerSource("nl");
    nlAsk.mutate(wellContextPrefix + queryText, {
      onSuccess: (data) => {
        // Ungrounded question with no current well selected: nothing
        // to fall back to, so let the hollow-answer UI explain why.
        if (isHollowAnswer(data) && selection) runStructuredFallback();
      },
      onError: (err) => {
        // If the server has no Groq configured, /query returns 503 —
        // gracefully fall back to a deterministic similar_wells query
        // for the current well so the demo path still returns evidence.
        const be = extractBackendError(err);
        if (be?.status === 503 && selection) runStructuredFallback();
      },
    });
  };

  // Structured chips bypass the LLM entirely for intents that map
  // cleanly onto a StructuredQuery — zero interpretation risk.
  // StructuredQuery rejects "contradictory" field combinations per
  // intent (extra="forbid" + per-intent allowlist in query/schema.py):
  // top_k is only accepted by similar_wells/similar_windows — sending
  // it for well_information/formation_information/geological_context
  // is a 422. Verified against the live backend for all four intents.
  const STRUCTURED_INTENTS_WITH_TOP_K = new Set(["similar_wells", "similar_windows"]);

  const askStructuredIntent = (intent: string) => {
    if (!selection) return;
    setLastAnswerSource("structured");
    structuredAsk.mutate({
      intent,
      target_dataset: selection.dataset,
      target_well_id: selection.well_id,
      ...(STRUCTURED_INTENTS_WITH_TOP_K.has(intent) ? { top_k: 5 } : {}),
    });
  };

  // Documents panel state
  const [docQuery, setDocQuery] = useState("");
  const docSearch = useDocumentSearch();

  // Evidence drawer state
  const [drawer, setDrawer] = useState<{ alert: Alert | null; assessment: RiskAssessment | null } | null>(null);
  const openEvidenceFor = (alert: Alert | null, assessment: RiskAssessment | null) => {
    setDrawer({ alert, assessment });
  };

  // Close the drawer on well change — its contents (alert/assessment)
  // belong to whichever well was current when it was opened, and would
  // otherwise linger and misattribute to the newly selected well.
  useEffect(() => {
    setDrawer(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection?.dataset, selection?.well_id]);

  const assessmentForType = (t: string) =>
    riskAssess.data?.assessments.find((a) => a.risk_type === t) ?? null;

  const contractLabel =
    health.data && health.data.database === "connected"
      ? "Connected · 17 endpoints available"
      : "Backend unreachable — start uvicorn on :8000";

  return (
    <AppShell>
      <div className="mx-auto max-w-[1600px] p-4 sm:p-5 lg:p-6" data-testid="engineer-dashboard">
        <div className="mb-5 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <SectionKicker>Operational intelligence workspace</SectionKicker>
              <StatusBadge tone="blue">
                <span className="size-1.5 rounded-full bg-blue-600" /> Authorized operational data
              </StatusBadge>
              {user && <StatusBadge tone="slate">{user.name}</StatusBadge>}
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              {section === "overview"
                ? "Investigation overview"
                : section.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}
            </h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-500">
              A traceable workspace for nearby wells, drilling events, risk evidence and formation
              context. Every value on this page is a direct read from the FastAPI backend.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Activity
              size={15}
              className={
                health.data?.database === "connected" ? "text-emerald-600" : "text-red-600"
              }
            />
            <span data-testid="engineer-contract-status">API: {contractLabel}</span>
          </div>
        </div>

        {/* Current well summary ------------------------------ */}
        <Card className="mb-4 rounded-none border-slate-200 shadow-sm" data-testid="current-well-summary">
          <CardContent className="p-0">
            <div className="flex flex-col justify-between gap-4 px-4 py-4 md:flex-row md:items-center">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center bg-slate-100 text-slate-500">
                  <MapPinned size={20} />
                </div>
                <div>
                  <SectionKicker>Current well</SectionKicker>
                  <p
                    className="mt-1 font-mono text-lg font-bold text-slate-800"
                    data-testid="current-well-name"
                  >
                    {selection
                      ? `${selection.well_id} (${selection.dataset})`
                      : "No well selected"}
                  </p>
                  <p className="text-xs text-slate-500">
                    {selection
                      ? "Backed by /wells/state"
                      : "Pick a well from the list to begin an investigation"}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs sm:grid-cols-4">
                <div>
                  <p className="text-slate-400">Field</p>
                  <p className="font-mono font-semibold text-slate-700">
                    {wellState.data?.field_name ?? "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">Formation</p>
                  <p className="font-mono font-semibold text-slate-700">
                    {wellState.data?.current_formation ?? "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">Depth (m)</p>
                  <p className="font-mono font-semibold text-slate-700">
                    {wellState.data?.current_depth_m != null
                      ? wellState.data.current_depth_m.toFixed(0)
                      : "—"}
                    {wellState.data?.is_simulated && (
                      <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800">
                        DEMO / SIMULATED
                      </span>
                    )}
                    {/* This backend has no live telemetry integration: every
                        non-simulated well resolves current_depth_m as a
                        copy of total_depth_m (see nearby/current_well.py).
                        Never let that read as a live measurement. */}
                    {!wellState.data?.is_simulated &&
                      wellState.data?.current_depth_m != null &&
                      wellState.data?.total_depth_m != null &&
                      wellState.data.current_depth_m === wellState.data.total_depth_m && (
                        <span
                          className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600"
                          data-testid="depth-no-telemetry-chip"
                        >
                          AT TOTAL DEPTH · NO LIVE TELEMETRY
                        </span>
                      )}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">Status</p>
                  <p className="font-mono font-semibold text-slate-700">
                    {wellState.data?.status ?? "—"}
                  </p>
                </div>
              </div>
            </div>
            {/* Only shown when total depth is a DIFFERENT figure from the
                Depth (m) field above — that field's own inline chip
                already covers the equal-value (today: always) case, so
                this avoids saying the same thing twice. */}
            {wellState.data?.total_depth_m != null &&
              wellState.data.current_depth_m !== wellState.data.total_depth_m && (
                <p className="border-t border-slate-100 px-4 py-2 text-[10px] uppercase tracking-wider text-slate-500">
                  Historical total depth on record: {wellState.data.total_depth_m.toFixed(0)} m —
                  not live drilling depth.
                </p>
              )}
          </CardContent>
        </Card>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.48fr)_minmax(340px,0.82fr)]">
          <div className="space-y-4">
            {/* Well search + list --------------------------- */}
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="well-intelligence-map-panel"
            >
              <PanelHeader
                icon={MapPinned}
                title="Well intelligence"
                detail={
                  wellsQuery.isLoading
                    ? "Loading wells…"
                    : `${wellsQuery.data?.count ?? 0} wells returned by /wells`
                }
              />
              <CardContent className="p-4">
                <WellMap
                  className="mb-3 h-80 w-full"
                  allWells={wellsQuery.data?.wells ?? []}
                  nearby={nearby.data?.results ?? []}
                  similar={similar.data?.results ?? []}
                  current={
                    selection
                      ? {
                          dataset: selection.dataset,
                          well_id: selection.well_id,
                          latitude: wellState.data?.latitude ?? null,
                          longitude: wellState.data?.longitude ?? null,
                        }
                      : null
                  }
                  onSelectWell={selectWell}
                />
                <div className="mb-3 flex flex-col gap-2 sm:flex-row">
                  <div className="relative flex-1">
                    <Search size={15} className="absolute left-3 top-3 text-slate-400" />
                    <Input
                      value={wellSearch}
                      onChange={(event) => setWellSearch(event.target.value)}
                      placeholder="Filter by well id, field or dataset…"
                      className="h-10 rounded-none border-slate-300 pl-9 text-sm"
                      data-testid="well-search-input"
                    />
                  </div>
                </div>
                {wellsQuery.isError && <ErrorLine err={wellsQuery.error} />}
                {wellsQuery.isLoading && (
                  <div className="space-y-2">
                    <Skel /> <Skel /> <Skel />
                  </div>
                )}
                <div
                  className="max-h-72 divide-y divide-slate-100 overflow-y-auto border border-slate-200"
                  data-testid="wells-list"
                >
                  {filteredWells.map((w) => {
                    const active =
                      selection?.dataset === w.dataset && selection?.well_id === w.well_id;
                    return (
                      <button
                        key={`${w.dataset}:${w.well_id}`}
                        onClick={() => selectWell(w.dataset, w.well_id)}
                        className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs transition ${
                          active
                            ? "bg-blue-50 text-blue-900"
                            : "bg-white text-slate-700 hover:bg-slate-50"
                        }`}
                        data-testid={`well-row-${w.well_id}`}
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="truncate font-mono font-semibold">{w.well_id}</span>
                            <span className="rounded bg-slate-200 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                              {w.dataset}
                            </span>
                          </div>
                          <p className="mt-0.5 truncate text-[11px] text-slate-500">
                            {w.field_name ?? "—"} · {w.discovery_name ?? "—"}
                          </p>
                        </div>
                        <span className="ml-2 shrink-0 font-mono text-[10px] text-slate-500">
                          {w.has_coordinates ? "coords" : "no coords"}
                        </span>
                      </button>
                    );
                  })}
                  {!wellsQuery.isLoading && filteredWells.length === 0 && (
                    <div className="p-3 text-xs text-slate-500">
                      No wells match this filter.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Nearby / Similar ---------------------------- */}
            <div className="grid gap-4 lg:grid-cols-2">
              <Card
                className="rounded-none border-slate-200 shadow-sm"
                data-testid="nearby-wells-panel"
              >
                <PanelHeader
                  icon={Network}
                  title="Nearby wells"
                  detail={
                    selection
                      ? `Radius 50 km · /wells/nearby`
                      : "Select a well to see offset wells"
                  }
                />
                <CardContent className="p-4">
                  {!selection && (
                    <p className="text-xs text-slate-500">Waiting for a current well.</p>
                  )}
                  {nearby.isLoading && <Skel h={80} />}
                  {nearby.isError && <ErrorLine err={nearby.error} />}
                  {nearby.data && nearby.data.results.length === 0 && (
                    <p className="text-xs text-slate-500">
                      No offset wells with coordinates found within 50 km.
                    </p>
                  )}
                  <ul className="space-y-1 text-xs" data-testid="nearby-list">
                    {nearby.data?.results.slice(0, 8).map((n) => (
                      <li
                        key={`${n.dataset}:${n.well_id}`}
                        className="flex items-center justify-between gap-2 border border-slate-200 bg-white px-2 py-1.5"
                      >
                        <button
                          onClick={() => selectWell(n.dataset, n.well_id)}
                          className="min-w-0 flex-1 text-left"
                        >
                          <span className="font-mono font-semibold text-slate-800">
                            {n.well_id}
                          </span>{" "}
                          <span className="text-slate-500">{n.dataset}</span>
                          <p className="truncate text-[11px] text-slate-500">
                            {n.field_name ?? "—"}
                          </p>
                        </button>
                        <span className="shrink-0 font-mono text-[10px] text-slate-500">
                          {n.distance_km.toFixed(1)} km
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>

              <Card
                className="rounded-none border-slate-200 shadow-sm"
                data-testid="similar-wells-panel"
              >
                <PanelHeader
                  icon={TableProperties}
                  title="Similar wells"
                  detail={selection ? "/wells/similar (pgvector cosine)" : "Waiting for a well"}
                />
                <CardContent className="p-4">
                  {!selection && (
                    <p className="text-xs text-slate-500">Waiting for a current well.</p>
                  )}
                  {similar.isLoading && <Skel h={80} />}
                  {similar.isError && <ErrorLine err={similar.error} />}
                  {similar.data && similar.data.results.length === 0 && (
                    <p className="text-xs text-slate-500">
                      No geologically similar wells returned.
                    </p>
                  )}
                  <ul className="space-y-1 text-xs" data-testid="similar-list">
                    {similar.data?.results.slice(0, 8).map((s) => (
                      <li
                        key={`${s.dataset}:${s.well_id}`}
                        className="flex items-center justify-between gap-2 border border-slate-200 bg-white px-2 py-1.5"
                      >
                        <button
                          onClick={() => selectWell(s.dataset, s.well_id)}
                          className="min-w-0 flex-1 text-left"
                        >
                          <span className="font-mono font-semibold text-slate-800">
                            {s.well_id}
                          </span>{" "}
                          <span className="text-slate-500">{s.dataset}</span>
                          <p className="text-[11px] text-slate-500">
                            windows pooled {s.windows_pooled}/{s.windows_total}
                          </p>
                        </button>
                        <span className="shrink-0 font-mono text-[10px] text-slate-500">
                          sim {s.similarity.toFixed(3)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </div>

            {/* Events timeline ------------------------------ */}
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="events-panel"
            >
              <PanelHeader
                icon={Waves}
                title="Historical drilling events"
                detail={
                  selection
                    ? `${events.data?.count ?? 0} on well · ${
                        correlated.data?.count ?? 0
                      } correlated`
                    : "Waiting for a current well"
                }
              />
              <CardContent className="p-4">
                {!selection && (
                  <p className="text-xs text-slate-500">Select a current well to see events.</p>
                )}
                {events.isLoading && <Skel h={100} />}
                {events.isError && <ErrorLine err={events.error} />}
                {events.data && events.data.events.length === 0 && (
                  <p className="text-xs text-slate-500">
                    No events recorded for this well. The event catalog is populated
                    deterministically from SODIR wellbore-history text; a well can simply have
                    no historical events.
                  </p>
                )}
                <ul className="space-y-1.5 text-xs">
                  {events.data?.events.slice(0, 12).map((ev, i) => {
                    const sevTone: "red" | "amber" | "blue" | "slate" =
                      ev.severity === "critical" || ev.severity === "high"
                        ? "red"
                        : ev.severity === "medium"
                          ? "amber"
                          : ev.severity === "low"
                            ? "blue"
                            : "slate";
                    return (
                      <li
                        key={i}
                        className="flex items-start gap-2 border border-slate-200 bg-white px-2 py-1.5"
                      >
                        <span className="mt-0.5">
                          <StatusBadge tone={sevTone}>{ev.severity}</StatusBadge>
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-baseline gap-x-2">
                            <span className="rounded bg-slate-200 px-1.5 py-0.5 font-mono text-[10px] text-slate-700">
                              {ev.event_type}
                            </span>
                            {ev.depth_start_m != null && (
                              <span className="font-mono text-[11px] text-slate-600">
                                {ev.depth_start_m.toFixed(0)} m
                              </span>
                            )}
                            <span className="text-[11px] text-slate-500">
                              {ev.formation ?? ""}
                            </span>
                          </div>
                          {ev.description && (
                            <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-600">
                              {ev.description}
                            </p>
                          )}
                          {ev.provenance?.extraction_method && (
                            <p className="mt-0.5 font-mono text-[10px] text-slate-400">
                              {ev.provenance.extraction_method} · conf{" "}
                              {(ev.provenance.extraction_confidence ?? 0).toFixed(2)}
                            </p>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
                {correlated.data && correlated.data.count > 0 && (
                  <p className="mt-3 text-[11px] text-slate-500">
                    Correlated view is available via /events/correlated ({correlated.data.count}{" "}
                    matches).
                  </p>
                )}
              </CardContent>
            </Card>

            {/* AI intelligence ------------------------------ */}
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="ai-intelligence-panel"
            >
              <PanelHeader
                icon={Sparkles}
                title="NWIS intelligence"
                detail={
                  selection
                    ? `Grounded to ${selection.well_id} — every question sent includes this well's context`
                    : "Select a well first — ungrounded questions can't be resolved"
                }
              />
              <CardContent className="p-4">
                <div className="mb-3 flex flex-wrap gap-1.5">
                  <span className="w-full text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Deterministic actions (no LLM — always reliable)
                  </span>
                  {[
                    { label: "Well information", intent: "well_information" },
                    { label: "Similar wells", intent: "similar_wells" },
                    { label: "Formation information", intent: "formation_information" },
                    { label: "Geological context", intent: "geological_context" },
                  ].map((chip) => (
                    <button
                      key={chip.intent}
                      className="rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] text-blue-800 hover:bg-blue-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-50 disabled:text-slate-400"
                      onClick={() => askStructuredIntent(chip.intent)}
                      disabled={!selection || answerPending}
                      data-testid="ai-structured-chip"
                    >
                      {chip.label}
                    </button>
                  ))}
                </div>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  <span className="w-full text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Open-ended questions (LLM — well context auto-attached)
                  </span>
                  {[
                    "Tell me about this well",
                    "What formations are present in this well?",
                    "Show me wells similar to the current well",
                  ].map((chip) => (
                    <button
                      key={chip}
                      className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700 hover:bg-blue-50 hover:text-blue-800"
                      onClick={() => setQueryText(chip)}
                      data-testid="ai-chip"
                    >
                      {chip}
                    </button>
                  ))}
                </div>
                <p className="mb-3 text-[11px] text-slate-500">
                  This assistant answers well identity, formation, similarity, and geological
                  context questions. For historical drilling events or risk/alert detail, see the{" "}
                  <span className="font-semibold text-slate-600">Historical drilling events</span> and{" "}
                  <span className="font-semibold text-slate-600">Risk &amp; alert station</span> panels
                  above — those already query the real event and risk data directly.
                </p>
                {selection && (
                  <p className="mb-2 font-mono text-[10px] text-slate-400" data-testid="ai-context-preview">
                    Context sent: “{wellContextPrefix}…”
                  </p>
                )}
                <div className="flex gap-2">
                  <Input
                    value={queryText}
                    onChange={(event) => setQueryText(event.target.value)}
                    placeholder="Ask about nearby wells, events, formations, risks…"
                    className="h-10 rounded-none border-slate-300"
                    data-testid="ai-query-input"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !answerPending) submitQuestion();
                    }}
                  />
                  <Button
                    className="h-10 rounded-none bg-blue-600"
                    data-testid="ai-query-submit-button"
                    onClick={submitQuestion}
                    disabled={answerPending || !queryText.trim()}
                  >
                    {answerPending ? "…" : "Ask"}
                  </Button>
                </div>
                {answerError && (
                  <div className="mt-3 border border-red-200 bg-red-50 p-3">
                    <ErrorLine err={answerError} />
                    <p className="mt-1 text-[11px] text-red-800">
                      If natural-language /query is unavailable, the panel falls back to
                      /query/structured for a deterministic result — you can also use a
                      deterministic action above.
                    </p>
                  </div>
                )}
                {answerData && isHollowAnswer(answerData) && !answerError && (
                  <div className="mt-3 border border-amber-200 bg-amber-50 p-3" data-testid="ai-hollow-answer">
                    <p className="text-xs font-semibold text-amber-900">
                      Could not resolve this question to a specific well.
                    </p>
                    <p className="mt-1 text-[11px] text-amber-800">
                      {selection
                        ? "Auto-retrying with structured resolution for the current well…"
                        : "Select a current well from the list on the left, then ask again."}
                    </p>
                  </div>
                )}
                {answerData && !isHollowAnswer(answerData) && (
                  <div className="mt-3 space-y-3" data-testid="ai-answer">
                    <div className="border border-slate-200 bg-white p-3 text-sm text-slate-800">
                      {answerData.answer || "No natural-language answer returned."}
                    </div>
                    {answerData.confidence_score && (
                      <div className="flex items-center gap-2 text-[11px] text-slate-600">
                        <span className="font-mono">
                          confidence {answerData.confidence_score.value.toFixed(2)}
                        </span>
                        <StatusBadge tone="slate">
                          {answerData.confidence_score.label}
                        </StatusBadge>
                        <span className="text-slate-500">
                          Heuristic indicator — not a probability.
                        </span>
                      </div>
                    )}
                    {answerData.rationale.length > 0 && (
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Rationale
                        </p>
                        <ol className="mt-1 list-inside list-decimal text-[11px] text-slate-700">
                          {answerData.rationale.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                    {answerData.provenance.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {answerData.provenance.map((p, i) => (
                          <StatusBadge key={i} tone="slate">
                            {p}
                          </StatusBadge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right column -------------------------------- */}
          <div className="space-y-4">
            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="risk-alert-station"
            >
              <PanelHeader
                icon={CircleAlert}
                title="Risk & alert station"
                detail={
                  selection
                    ? "Evidence-based — see methodology in the drawer"
                    : "Waiting for a current well"
                }
              />
              <CardContent className="space-y-2 p-3">
                {!selection && (
                  <p className="px-1 pb-1 text-xs text-slate-500">
                    Select a current well to compute risk.
                  </p>
                )}
                {riskAssess.isLoading && <Skel h={80} />}
                {riskAssess.isError && <ErrorLine err={riskAssess.error} />}
                {riskAssess.data?.assessments.map((a, index) => (
                  <button
                    key={a.risk_type}
                    onClick={() => openEvidenceFor(null, a)}
                    className="group flex w-full items-center gap-3 border border-slate-200 bg-white p-3 text-left transition-colors duration-150 hover:border-blue-300 hover:bg-blue-50/40"
                    data-testid={`risk-category-${index + 1}`}
                  >
                    <div className="flex size-8 items-center justify-center bg-slate-100 text-slate-500 group-hover:bg-blue-100 group-hover:text-blue-600">
                      <CircleAlert size={16} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-semibold capitalize text-slate-800">
                          {a.risk_type.replace(/_/g, " ")}
                        </p>
                        <span className="font-mono text-[10px] text-slate-500">
                          {a.score.toFixed(3)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <LevelBadge level={a.level} />
                        <span className="text-[11px] text-slate-500">
                          {a.evidence[0]?.slice(0, 60) ?? "No supporting evidence."}
                        </span>
                      </div>
                    </div>
                    <ArrowUpRight
                      size={15}
                      className="text-slate-400 transition-transform duration-150 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                    />
                  </button>
                ))}
                <p className="px-1 pt-2 text-[10px] leading-relaxed text-slate-400">
                  Scores are heuristic evidence indicators, never calibrated probabilities.
                </p>

                {/* Alerts subsection */}
                {riskAlerts.data && riskAlerts.data.count > 0 && (
                  <div className="mt-2 border-t border-slate-100 pt-2">
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      Active alerts ({riskAlerts.data.count})
                    </p>
                    <ul className="space-y-1.5">
                      {riskAlerts.data.alerts.map((al) => {
                        const assessment =
                          assessmentForType(al.alert_type) ?? null;
                        return (
                          <li key={al.alert_id ?? al.title}>
                            <button
                              onClick={() => openEvidenceFor(al, assessment)}
                              className="flex w-full items-start gap-2 border border-slate-200 bg-white p-2 text-left text-xs hover:border-blue-300"
                              data-testid="alert-row"
                            >
                              <StatusBadge
                                tone={
                                  al.severity === "critical" || al.severity === "high"
                                    ? "red"
                                    : al.severity === "warning"
                                      ? "amber"
                                      : "blue"
                                }
                              >
                                {String(al.severity)}
                              </StatusBadge>
                              <div className="min-w-0 flex-1">
                                <p className="truncate font-semibold text-slate-800">
                                  {al.title}
                                </p>
                                <p className="line-clamp-2 text-[11px] text-slate-500">
                                  {al.explanation}
                                </p>
                              </div>
                              <ArrowUpRight size={13} className="mt-0.5 text-slate-400" />
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="document-vault-panel"
            >
              <PanelHeader
                icon={BookOpen}
                title="Document & knowledge vault"
                detail="Authorized source search — POST /documents/search"
              />
              <CardContent className="p-4">
                <div className="mb-3 flex gap-2">
                  <div className="relative flex-1">
                    <FileSearch size={15} className="absolute left-3 top-3 text-slate-400" />
                    <Input
                      value={docQuery}
                      onChange={(e) => setDocQuery(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && docQuery.trim())
                          docSearch.mutate({ query: docQuery, top_k: 5 });
                      }}
                      placeholder="Semantic search over document chunks…"
                      className="h-9 rounded-none border-slate-300 pl-9 text-sm"
                      data-testid="doc-search-input"
                    />
                  </div>
                  <Button
                    onClick={() => docSearch.mutate({ query: docQuery, top_k: 5 })}
                    disabled={!docQuery.trim() || docSearch.isPending}
                    className="h-9 rounded-none bg-blue-600"
                    data-testid="doc-search-submit-button"
                  >
                    {docSearch.isPending ? "…" : "Search"}
                  </Button>
                </div>
                {docSearch.isError && <ErrorLine err={docSearch.error} />}
                {docSearch.data && docSearch.data.count === 0 && (
                  <p className="text-xs text-slate-500">No document chunks matched this query.</p>
                )}
                <ul className="space-y-1.5">
                  {(docSearch.data?.results ?? []).map((chunk: DocumentChunk) => (
                    <li
                      key={chunk.chunk_id}
                      className="border border-slate-200 bg-white p-2 text-xs"
                    >
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <span className="truncate font-mono font-semibold text-slate-800">
                          {chunk.file_name}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-slate-500">
                          sim {chunk.similarity.toFixed(3)}
                          {chunk.page_number != null && ` · p.${chunk.page_number}`}
                        </span>
                      </div>
                      <p className="line-clamp-3 text-[11px] text-slate-600">{chunk.text}</p>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card
              className="rounded-none border-slate-200 shadow-sm"
              data-testid="provenance-panel"
            >
              <CardHeader className="border-b border-slate-200 px-4 py-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <TableProperties size={16} className="text-blue-600" /> Provenance ledger
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400">Well</p>
                    <p className="mt-1 font-mono font-semibold text-slate-700">
                      {selection?.well_id ?? "—"}
                    </p>
                  </div>
                  <div className="border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400">
                      Dataset
                    </p>
                    <p className="mt-1 font-mono font-semibold text-slate-700">
                      {selection?.dataset ?? "—"}
                    </p>
                  </div>
                  <div className="border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400">
                      SODIR wellbore id
                    </p>
                    <p className="mt-1 font-mono font-semibold text-slate-700">
                      {wellState.data?.dataset ? (
                        <>{(wellState.data as unknown as { sodir_wellbore_id?: number }).sodir_wellbore_id ?? "—"}</>
                      ) : (
                        "—"
                      )}
                    </p>
                  </div>
                  <div className="border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400">
                      Timestamp
                    </p>
                    <p className="mt-1 font-mono font-semibold text-slate-700">
                      {wellState.data
                        ? new Date(wellState.data.timestamp).toISOString().slice(0, 19)
                        : "—"}
                    </p>
                  </div>
                </div>
                <p className="mt-3 text-xs leading-relaxed text-slate-500">
                  Every value on this page is a direct read from a backend endpoint. Historical
                  events and risk assessments carry their own provenance blocks — open the
                  evidence drawer to see them.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

        <EvidenceDrawer
          open={!!drawer}
          onClose={() => setDrawer(null)}
          alert={drawer?.alert ?? null}
          assessment={drawer?.assessment ?? null}
        />
      </div>
    </AppShell>
  );
}
