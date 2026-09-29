/**
 * NWIS capability registry.
 *
 * The current running OpenAPI schema does not expose these routes, so this
 * registry deliberately contains endpoint metadata only. Response interfaces
 * and apiGet/apiPost adapters must be added in the same edit as the confirmed
 * OpenAPI contract; no response fields are inferred here.
 */
export type NwisCapabilityKey =
  | "wells"
  | "wellLookup"
  | "nearbyWells"
  | "similarWells"
  | "events"
  | "riskAssessment"
  | "riskAlerts"
  | "query"
  | "documents"
  | "health"
  | "users"
  | "ingestion"
  | "database"
  | "audit";

export interface NwisCapability {
  key: NwisCapabilityKey;
  label: string;
  endpoint: string;
  method: "GET" | "POST";
  area: "engineer" | "admin";
  status: "unconfirmed";
  responseContract: "pending-openapi";
}

const capability = (
  key: NwisCapabilityKey,
  label: string,
  endpoint: string,
  method: NwisCapability["method"],
  area: NwisCapability["area"],
): NwisCapability => ({ key, label, endpoint, method, area, status: "unconfirmed", responseContract: "pending-openapi" });

export const NWIS_API_CAPABILITIES: Record<NwisCapabilityKey, NwisCapability> = {
  wells: capability("wells", "Well records", "/wells", "GET", "engineer"),
  wellLookup: capability("wellLookup", "Well lookup", "/wells/lookup", "GET", "engineer"),
  nearbyWells: capability("nearbyWells", "Nearby wells", "/wells/nearby", "GET", "engineer"),
  similarWells: capability("similarWells", "Similar wells", "/wells/similar", "GET", "engineer"),
  events: capability("events", "Historical events", "/events/well · /events/correlated", "GET", "engineer"),
  riskAssessment: capability("riskAssessment", "Risk assessment", "/risk/assess", "GET", "engineer"),
  riskAlerts: capability("riskAlerts", "Risk alerts & evidence", "/risk/alerts", "GET", "engineer"),
  query: capability("query", "NWIS intelligence query", "/query", "POST", "engineer"),
  documents: capability("documents", "Document search", "/documents/search · /documents/{document_id}", "POST", "engineer"),
  health: capability("health", "System health", "/health", "GET", "admin"),
  users: capability("users", "Users & roles", "/users · /roles", "GET", "admin"),
  ingestion: capability("ingestion", "Ingestion pipeline", "/ingestion/status", "GET", "admin"),
  database: capability("database", "Database health", "/database/health", "GET", "admin"),
  audit: capability("audit", "Audit logs", "/audit/logs", "GET", "admin"),
};

export function nwisCapability(key: NwisCapabilityKey): NwisCapability {
  return NWIS_API_CAPABILITIES[key];
}