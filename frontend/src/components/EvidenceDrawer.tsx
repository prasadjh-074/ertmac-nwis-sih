import { ArrowRight, CircleAlert, X } from "@/lib/lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./StatusBadge";
import type { Alert, RiskAssessment } from "@/api/backend-types";

// Legacy placeholder API (still supported by callers that haven't been
// wired to the real backend yet).
export interface EvidenceViewState {
  status: "unavailable";
  title: string;
  subtitle: string;
  endpoint: string;
  message: string;
  cards: readonly { label: string; value: string }[];
}

type Tone = "blue" | "green" | "amber" | "red" | "slate";

function severityTone(sev: string): Tone {
  const s = (sev ?? "").toLowerCase();
  if (s === "critical" || s === "high") return "red";
  if (s === "warning" || s === "medium") return "amber";
  if (s === "info" || s === "low") return "blue";
  return "slate";
}

interface EvidenceDrawerProps {
  open: boolean;
  onClose: () => void;
  /** Real alert payload from GET /risk/alerts. */
  alert?: Alert | null;
  /** Optional matching risk assessment from GET /risk/assess — surfaces
   *  methodology, limitations, contributing_features, and historical
   *  events in the same drawer. */
  assessment?: RiskAssessment | null;
  /** Legacy fallback for pages not yet wired to the real backend. */
  evidence?: EvidenceViewState;
}

export function EvidenceDrawer({ open, onClose, alert, assessment, evidence }: EvidenceDrawerProps) {
  if (!open) return null;

  const hasRealData = !!(alert || assessment);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="evidence-drawer">
      <button
        aria-label="Close evidence drawer"
        className="absolute inset-0 cursor-default bg-slate-900/20"
        onClick={onClose}
        data-testid="evidence-drawer-backdrop"
      />
      <aside
        className="relative h-full w-full max-w-xl animate-in slide-in-from-right border-l border-slate-200 bg-white shadow-2xl duration-300"
        aria-label="Why this alert"
      >
        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2">
              <CircleAlert size={16} className="text-amber-600" />
              {alert ? (
                <StatusBadge tone={severityTone(alert.severity)}>
                  {String(alert.severity).toUpperCase()}
                </StatusBadge>
              ) : assessment ? (
                <StatusBadge tone={severityTone(assessment.level)}>
                  {String(assessment.level).toUpperCase()}
                </StatusBadge>
              ) : null}
              {!hasRealData && <StatusBadge tone="amber">Future endpoint</StatusBadge>}
            </div>
            <h2
              className="text-xl font-bold tracking-tight text-slate-900"
              data-testid="evidence-drawer-title"
            >
              {alert?.title ?? (assessment ? `Why: ${assessment.risk_type.replace(/_/g, " ")}` : (evidence?.title ?? "Why this alert?"))}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {alert?.explanation ?? (evidence?.subtitle ?? "Contributing evidence for the selected risk.")}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close evidence drawer"
            data-testid="evidence-drawer-close-button"
          >
            <X size={18} />
          </Button>
        </div>

        <div className="space-y-6 overflow-y-auto p-6" style={{ maxHeight: "calc(100vh - 108px)" }}>
          {/* Real-data path ------------------------------------- */}
          {hasRealData && (
            <>
              {alert?.recommended_action && (
                <section className="border border-blue-200 bg-blue-50 p-4" data-testid="evidence-recommended-action">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-blue-700">
                    Decision support only — not autonomous control
                  </p>
                  <p className="mt-2 text-sm font-medium text-blue-950">{alert.recommended_action}</p>
                </section>
              )}

              {(alert?.evidence?.length ?? 0) > 0 && (
                <section data-testid="evidence-list">
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Contributing evidence
                  </p>
                  <ul className="space-y-1.5 text-sm text-slate-700">
                    {alert!.evidence.map((line, i) => (
                      <li key={i} className="border-l-2 border-slate-300 pl-3">
                        {line}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {assessment && (
                <section data-testid="evidence-methodology">
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Methodology
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="border border-slate-200 bg-slate-50 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-slate-400">Method</p>
                      <p className="mt-1 font-mono text-sm font-semibold text-slate-800">
                        {assessment.methodology}
                      </p>
                    </div>
                    <div className="border border-slate-200 bg-slate-50 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-slate-400">Source</p>
                      <p className="mt-1 font-mono text-sm font-semibold text-slate-800">
                        {assessment.model_or_rule_source}
                      </p>
                    </div>
                    <div className="border border-slate-200 bg-slate-50 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-slate-400">
                        Evidence score
                      </p>
                      <p className="mt-1 font-mono text-sm font-semibold text-slate-800">
                        {assessment.score.toFixed(3)}{" "}
                        <span className="text-[10px] text-slate-500">not a probability</span>
                      </p>
                    </div>
                    <div className="border border-slate-200 bg-slate-50 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-slate-400">
                        Confidence indicator
                      </p>
                      <p className="mt-1 font-mono text-sm font-semibold text-slate-800">
                        {assessment.confidence.toFixed(3)}
                      </p>
                    </div>
                  </div>
                </section>
              )}

              {assessment && assessment.historical_events?.length > 0 && (
                <section data-testid="evidence-historical-events">
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Historical events ({assessment.historical_events.length})
                  </p>
                  <div className="max-h-60 space-y-1.5 overflow-y-auto pr-1">
                    {assessment.historical_events.map((row, i) => {
                      const r = row as Record<string, unknown>;
                      return (
                        <div key={i} className="border border-slate-200 bg-slate-50 p-2 text-xs">
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span className="font-mono font-semibold text-slate-800">
                              {String(r.well_id ?? "—")}
                            </span>
                            <span className="text-slate-500">{String(r.dataset ?? "")}</span>
                            <span className="rounded bg-slate-200 px-1.5 py-0.5 font-mono text-[10px] text-slate-700">
                              {String(r.event_type ?? "")}
                            </span>
                            <span className="text-slate-500">
                              {r.depth_m != null ? `${r.depth_m} m` : ""}
                            </span>
                            <span className="text-slate-500">{String(r.formation ?? "")}</span>
                            {r.distance_km != null && (
                              <span className="font-mono text-[10px] text-slate-500">
                                {Number(r.distance_km).toFixed(1)} km
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {assessment && assessment.limitations.length > 0 && (
                <section data-testid="evidence-limitations">
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-amber-600">
                    Limitations
                  </p>
                  <ul className="space-y-1 text-xs text-amber-900">
                    {assessment.limitations.map((l, i) => (
                      <li key={i} className="border-l-2 border-amber-300 pl-3">
                        {l}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {alert?.provenance && alert.provenance.length > 0 && (
                <section data-testid="evidence-provenance">
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Provenance
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {alert.provenance.map((p, i) => (
                      <span
                        key={i}
                        className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[10px] text-slate-600"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}

          {/* Legacy placeholder path ---------------------------- */}
          {!hasRealData && evidence && (
            <>
              <section
                data-testid="evidence-drawer-empty-state"
                className="border border-amber-200 bg-amber-50 p-4"
              >
                <p className="text-sm font-semibold text-amber-900">{evidence.message}</p>
                <p className="mt-1 text-xs leading-relaxed text-amber-800">
                  Select an alert with confirmed evidence to view real risk methodology and
                  provenance here.
                </p>
              </section>
              <div className="grid gap-3 sm:grid-cols-2">
                {evidence.cards.map(({ label, value }) => (
                  <div
                    key={label}
                    className="border border-slate-200 bg-slate-50 p-3"
                    data-testid={`evidence-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                  >
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      {label}
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-700">{value}</p>
                  </div>
                ))}
              </div>
              <code
                className="block border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-[10px] text-slate-500"
                data-testid="evidence-drawer-endpoint"
              >
                {evidence.endpoint}
              </code>
              <div className="flex items-center gap-2 border-t border-slate-200 pt-5 text-xs text-slate-500">
                <ArrowRight size={14} className="text-blue-600" />
                When the backend exposes evidence, related wells can be highlighted without
                inventing IDs.
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
