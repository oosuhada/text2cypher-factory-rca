export type QueryStatus =
  | "success"
  | "empty"
  | "blocked"
  | "failed"
  | "needs_clarification"
  | "unsupported";

export type EvidenceNode = {
  id: string;
  label?: string;
  labels?: string[];
  properties: Record<string, unknown>;
};

export type EvidenceRelationship = {
  id?: string;
  type: string;
  source: string;
  target: string;
  properties?: Record<string, unknown>;
};

export type Evidence = {
  nodes: EvidenceNode[];
  relationships: EvidenceRelationship[];
  node_count: number;
  relationship_count: number;
  truncated?: Record<string, boolean> | boolean;
};

export type QueryResponse = {
  project_id?: string;
  question: string;
  answer: string;
  status: QueryStatus;
  cypher: string;
  rows: Record<string, unknown>[];
  row_count: number;
  evidence: Evidence;
  validation: {
    attempts: number;
    errors: string[];
    trace: Record<string, unknown>[];
    elapsed_ms: number;
  };
  usage: Record<string, number>;
  caveat?: string | null;
  provider: string;
  fallback_reason?: string | null;
};

export type StoredConversation = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  question: string;
  response: QueryResponse;
  projectId: string;
};

export type Project = {
  project_id: string;
  name: string;
  domain_type: string;
  dataset_name: string;
  schema_version: string | null;
  status: "draft" | "mapping_ready" | "ready" | "archived";
  created_at: string;
  updated_at: string;
  is_active: boolean;
};

export type ProjectReadiness = {
  project_id: string;
  lifecycle_status: Project["status"];
  upload_count: number;
  mapping_approved: boolean;
  schema_available: boolean;
  node_count: number;
  relationship_count: number;
  can_query: boolean;
  can_load: boolean;
  next_action: "upload" | "map" | "load" | "query";
};

export type DatasetProfile = {
  upload_id: string;
  project_id: string;
  created_at: string;
  status: string;
  total_bytes: number;
  files: {
    filename: string;
    row_count: number;
    column_count: number;
    columns: {
      name: string;
      inferred_type: string;
      missing_count: number;
      missing_rate: number;
      unique_count: number;
      identity_candidate: boolean;
      samples: unknown[];
    }[];
  }[];
};

export type HealthResponse = {
  status: "ready" | "degraded";
  checks: {
    check: string;
    status: string;
    detail: string;
    required: boolean;
  }[];
};

export type GraphSchema = {
  project_id: string;
  schema_version: string;
  title: string;
  schema_context: string;
  node_identities: {
    label: string;
    identity_property: string;
  }[];
  relationship_types: string[];
  nodes: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
};

export type NodeSearchResponse = {
  label: string;
  query: string;
  identity_property: string;
  nodes: EvidenceNode[];
  count: number;
};

export type FeedbackDecision =
  | "verified"
  | "disputed"
  | "needs_followup";

export type FeedbackRecord = {
  review_id: string;
  timestamp: string;
  query_fingerprint: string;
  question: string;
  cypher: string;
  query_status: string;
  provider: string;
  row_count: number;
  decision: FeedbackDecision;
  reviewer: string;
  note: string;
};

export type FeedbackSummary = {
  total_reviews: number;
  unique_queries_reviewed: number;
  decision_counts: Record<FeedbackDecision, number>;
  recent: FeedbackRecord[];
  storage: string;
};

export type SubgraphResponse = {
  root: EvidenceNode | null;
  nodes: EvidenceNode[];
  relationships: EvidenceRelationship[];
  node_count: number;
  relationship_count: number;
  depth: number;
  truncated: boolean;
};
