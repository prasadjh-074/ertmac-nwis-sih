import { CircleDashed, PlugZap } from "@/lib/lucide-react";
import { nwisCapability, type NwisCapabilityKey } from "@/api/nwis";
import { MockBadge } from "./StatusBadge";

const engineerKeys: NwisCapabilityKey[] = ["wells", "wellLookup", "nearbyWells", "similarWells", "events", "riskAssessment", "riskAlerts", "query", "documents"];
const adminKeys: NwisCapabilityKey[] = ["health", "users", "ingestion", "database", "audit"];

export function ApiContractMatrix({ scope }: { scope: "engineer" | "admin" }) {
  const keys = scope === "engineer" ? engineerKeys : adminKeys;
  return (
    <div className="border border-slate-200 bg-white shadow-sm" data-testid={`nwis-api-contract-matrix-${scope}`}>
      <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="flex items-start gap-2.5"><PlugZap size={17} className="mt-0.5 text-blue-600" /><div><p className="text-sm font-bold text-slate-900">NWIS API wiring</p><p className="mt-0.5 text-xs text-slate-500">Endpoint registry prepared; response schemas are gated on OpenAPI confirmation.</p></div></div>
        <MockBadge future />
      </div>
      <div className="grid gap-2 p-3 sm:grid-cols-2 xl:grid-cols-3">
        {keys.map((key) => {
          const item = nwisCapability(key);
          return <div key={key} className="flex items-start gap-2 border border-slate-200 bg-slate-50 px-3 py-2" data-testid={`nwis-api-capability-${key}`}><CircleDashed size={14} className="mt-0.5 shrink-0 text-amber-600" /><div className="min-w-0"><p className="truncate text-xs font-semibold text-slate-700">{item.label}</p><code className="mt-1 block truncate font-mono text-[10px] text-slate-400">{item.method} {item.endpoint}</code></div></div>;
        })}
      </div>
    </div>
  );
}