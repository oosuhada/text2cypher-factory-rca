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
  schema_context: string;
  node_identities: {
    label: string;
    identity_property: string;
  }[];
  relationship_types: string[];
};

export type NodeSearchResponse = {
  label: string;
  query: string;
  identity_property: string;
  nodes: EvidenceNode[];
  count: number;
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
