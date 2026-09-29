/**
 * TypeScript mirrors of the confirmed FastAPI response models
 * (see api/schemas.py + api/routers/* in the backend repo).
 *
 * Every shape here is a hand-typed mirror of a Pydantic model —
 * nothing is inferred, nothing is invented. If the backend changes
 * a field, update it here in the same commit.
 */

// ── Structured error envelope (from api/errors.py) ─────────────
export interface APIErrorBody {
  error: {
    type: string;
    message: string;
    status: number;
    request_id: string | null;
    detail?: unknown;
  };
}

// ── /health ────────────────────────────────────────────────────
export interface HealthResponse {
  status: string; // "ok"
  version: string;
  database: string; // "connected" | "unreachable"
}

// ── Wells ──────────────────────────────────────────────────────
export interface WellLocationResponse {
  well_id: string;
  dataset: string;
  latitude: number | null;
  longitude: number | null;
  has_coordinates: boolean;
  sodir_wellbore_id: number | null;
  sodir_wellbore_name: string | null;
  field_name: string | null;
  discovery_name: string | null;
}

export interface WellListResponse {
  count: number;
  wells: WellLocationResponse[];
}

export interface NearbyWellResponse {
  well_id: string;
  dataset: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  sodir_wellbore_id: number | null;
  sodir_wellbore_name: string | null;
  field_name: string | null;
  discovery_name: string | null;
  rank: number;
}

export interface NearbyWellListResponse {
  reference_well: string;
  reference_dataset: string;
  radius_km: number;
  count: number;
  results: NearbyWellResponse[];
}

export interface SimilarWellResponse {
  well_id: string;
  dataset: string;
  similarity: number;
  rank: number;
  windows_total: number;
  windows_pooled: number;
  pooling_fraction: number;
}

export interface SimilarWellListResponse {
  reference_well: string;
  reference_dataset: string;
  count: number;
  results: SimilarWellResponse[];
}

export interface ContextResponse {
  well_id: string;
  dataset: string;
  latitude: number | null;
  longitude: number | null;
  field_name: string | null;
  discovery_name: string | null;
  sodir_wellbore_id: number | null;
  total_depth_m: number | null;
  status: string | null;
  operator: string | null;
  nearby_well_count: number;
  similar_well_count: number;
  nearby_wells: NearbyWellResponse[];
  similar_wells: SimilarWellResponse[];
}

export interface CurrentWellStateResponse {
  well_id: string;
  dataset: string;
  timestamp: string; // ISO
  latitude: number | null;
  longitude: number | null;
  current_depth_m: number | null;
  current_formation: string | null;
  total_depth_m: number | null;
  status: string | null;
  operator: string | null;
  field_name: string | null;
  drilling_parameters: Record<string, unknown>;
  is_simulated: boolean;
}

// ── Events ─────────────────────────────────────────────────────
export type EventSeverity = "low" | "medium" | "high" | "critical" | "unknown" | string;

export interface EventProvenance {
  source_type: string | null;
  source_table: string | null;
  extraction_method: string | null;
  extraction_confidence: number | null;
  raw_text_snippet: string | null;
}

export interface DrillingEventItem {
  event_type: string;
  severity: EventSeverity;
  description: string | null;
  depth_start_m: number | null;
  depth_end_m: number | null;
  formation: string | null;
  well_id: string | null;
  dataset: string | null;
  subtype: string | null;
  provenance: EventProvenance | null;
}

export interface EventListResponse {
  count: number;
  events: DrillingEventItem[];
}

export interface CorrelatedEventItem {
  event: DrillingEventItem;
  source_well_id: string;
  source_dataset: string;
  distance_km: number | null;
  depth_overlap: boolean;
  depth_difference_m: number | null;
  formation_match: boolean;
  relevance_factors: Record<string, unknown>;
}

export interface CorrelatedEventListResponse {
  reference_well: string;
  reference_dataset: string;
  count: number;
  events: CorrelatedEventItem[];
}

// ── Risk ───────────────────────────────────────────────────────
export type RiskLevel = "low" | "medium" | "high" | "unknown";
export type RiskType =
  | "mud_loss_risk"
  | "stuck_pipe_risk"
  | "kick_overpressure_risk"
  | "torque_spike_risk"
  | "cementing_risk";

export interface RiskAssessment {
  risk_type: RiskType;
  score: number;
  level: RiskLevel;
  confidence: number;
  evidence: string[];
  contributing_features: Record<string, unknown>;
  historical_events: Record<string, unknown>[];
  methodology: string; // "evidence_rule_based" | "model_based"
  limitations: string[];
  model_or_rule_source: string;
}

export interface RuleResult {
  rule_type: string;
  triggered: boolean;
  severity: RiskLevel;
  evidence: string[];
  contributing_events: Record<string, unknown>[];
  details: Record<string, unknown>;
}

export interface RiskAssessResponse {
  well_id: string;
  dataset: string;
  current_depth_m: number | null;
  current_formation: string | null;
  correlated_event_count: number;
  assessments: RiskAssessment[];
  rules: RuleResult[];
}

export type AlertSeverity = "info" | "warning" | "high" | "critical" | string;

export interface Alert {
  alert_id: number | null;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  explanation: string;
  evidence: string[];
  recommended_action: string;
  provenance: string[];
  context: Record<string, unknown>;
}

export interface AlertListResponse {
  well_id: string;
  dataset: string;
  count: number;
  alerts: Alert[];
}

// ── Query (LangGraph) ──────────────────────────────────────────
export interface EvidenceItem {
  source_system: string;
  entity_type: string;
  well_id?: string | null;
  source_id?: string | null;
  similarity?: number | null;
  metadata?: Record<string, unknown>;
}

export interface ConfidenceScore {
  value: number;
  label: string;
  factors: Record<string, unknown>;
  basis: string[];
  note: string;
  is_probability: false;
}

export interface ExecutionMetadata {
  total_execution_ms?: number;
  intent?: string;
  result_count?: number;
  data_sources?: string[];
  llm_used?: boolean;
  node_status?: Record<string, string>;
  document_result_count?: number;
}

export interface GraphError {
  stage?: string;
  error_type?: string;
  message?: string;
}

export interface QueryResponseBody {
  answer: string;
  structured_query: Record<string, unknown> | null;
  evidence: EvidenceItem[];
  confidence_score: ConfidenceScore | null;
  rationale: string[];
  provenance: string[];
  metadata: ExecutionMetadata;
  errors: GraphError[];
  risk_assessments: RiskAssessment[];
  alerts: Alert[];
}

// ── Documents ──────────────────────────────────────────────────
export interface DocumentChunk {
  chunk_id: string;
  document_id: string;
  file_name: string;
  page_number: number | null;
  chunk_index: number;
  section: string | null;
  text: string;
  similarity: number;
  rank: number;
}

export interface DocumentSearchResponse {
  query: string;
  count: number;
  results: DocumentChunk[];
}

export interface PageHandwritingSummary {
  page_number: number;
  used_ocr: boolean;
  ocr_confidence: number | null;
  handwriting_classification: "typed" | "handwritten" | "mixed" | "unknown" | null;
  handwriting_confidence: number | null;
  handwriting_ocr_status: string | null;
  source_content_type: string | null;
}

export interface DocumentMetadataResponse {
  document_id: string;
  file_name: string;
  source_type: "pdf" | "text" | "image" | string;
  page_count: number | null;
  handwriting_detected: boolean;
  handwriting_page_count: number;
  pages: PageHandwritingSummary[];
}
