// Mirrors api/schemas.py and api/routers/*.py response models.
export type Dataset = "FORCE_2020" | "VOLVE";

export interface WellRef {
  dataset: string;
  well_id: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
}

export interface WellLocation {
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
  wells: WellLocation[];
}

export interface NearbyWell {
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
  results: NearbyWell[];
}

export interface SimilarWell {
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
  results: SimilarWell[];
}

export interface WellContextResponse {
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
  nearby_wells: NearbyWell[];
  similar_wells: SimilarWell[];
}

export interface WellStateResponse {
  well_id: string;
  dataset: string;
  timestamp: string;
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

export interface EventProvenance {
  source_type?: string | null;
  source_table?: string | null;
  extraction_method?: string | null;
  extraction_confidence?: number | null;
  raw_text_snippet?: string | null;
}

export interface DrillingEvent {
  event_type: string;
  severity: string;
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
  events: DrillingEvent[];
}

export interface CorrelatedEvent {
  event: DrillingEvent;
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
  events: CorrelatedEvent[];
}

export type HistoricalEventRecord = Record<string, unknown>;

export interface RiskAssessment {
  risk_type: string;
  score: number;
  level: string;
  confidence: number;
  evidence: string[];
  contributing_features: Record<string, unknown>;
  historical_events: HistoricalEventRecord[];
  methodology: string;
  limitations: string[];
  model_or_rule_source: string;
}

export interface RuleResult {
  rule_type: string;
  triggered: boolean;
  severity: string;
  evidence: string[];
  contributing_events: HistoricalEventRecord[];
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

export interface Alert {
  alert_id: number | null;
  alert_type: string;
  severity: string;
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

export interface EvidenceItem {
  source_system?: string;
  entity_type?: string;
  well_id?: string | null;
  source_id?: string | null;
  similarity?: number | null;
  metadata?: Record<string, unknown>;
  [k: string]: unknown;
}

export interface ConfidenceScore {
  value: number;
  label: string;
  factors?: Record<string, unknown>;
  basis?: string[];
  note?: string;
  is_probability?: boolean;
}

export interface QueryError {
  stage?: string;
  error_type?: string;
  message?: string;
  [k: string]: unknown;
}

export interface QueryResponse {
  answer: string;
  structured_query: Record<string, unknown> | null;
  evidence: EvidenceItem[];
  confidence_score: ConfidenceScore | null;
  rationale: string[];
  provenance: string[];
  metadata: {
    total_execution_ms?: number;
    intent?: string;
    result_count?: number;
    data_sources?: string[];
    llm_used?: boolean;
    node_status?: Record<string, string>;
    document_result_count?: number;
    [k: string]: unknown;
  };
  errors: QueryError[];
  risk_assessments: Record<string, unknown>[];
  alerts: Record<string, unknown>[];
}

export type StructuredIntent =
  | "similar_wells"
  | "well_information"
  | "formation_information"
  | "geological_context"
  | "document_search";

export interface StructuredQuery {
  intent: StructuredIntent;
  target_dataset?: string;
  target_well_id?: string;
  top_k?: number;
  search_text?: string;
}

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

export interface DocumentSearchRequest {
  query: string;
  top_k?: number;
  source_type?: "pdf" | "text" | "image";
  file_name?: string;
}

export interface DocumentSearchResponse {
  query: string;
  count: number;
  results: DocumentChunk[];
}

export interface PageHandwriting {
  page_number: number;
  used_ocr: boolean;
  ocr_confidence: number | null;
  handwriting_classification: string | null;
  handwriting_confidence: number | null;
  handwriting_ocr_status: string | null;
  source_content_type: string | null;
}

export interface DocumentMetadata {
  document_id: string;
  file_name: string;
  source_type: string;
  page_count: number | null;
  handwriting_detected: boolean;
  handwriting_page_count: number;
  pages: PageHandwriting[];
}
