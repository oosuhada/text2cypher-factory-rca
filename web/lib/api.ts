import type {
  FeedbackDecision,
  FeedbackRecord,
  FeedbackSummary,
  GraphSchema,
  HealthResponse,
  NodeSearchResponse,
  QueryResponse,
  SubgraphResponse,
} from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(
  pathname: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${pathname}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message =
      payload?.detail ??
      `API 요청이 실패했습니다. (${response.status})`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function queryFactoryGraph(question: string) {
  return request<QueryResponse>("/api/v1/query", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function getHealth() {
  return request<HealthResponse>("/api/v1/health");
}

export function getMetrics() {
  return request<Record<string, unknown>>("/api/v1/metrics");
}

export function submitExpertFeedback(payload: {
  question: string;
  cypher: string;
  query_status: string;
  provider: string;
  row_count: number;
  decision: FeedbackDecision;
  reviewer: string;
  note: string;
}) {
  return request<FeedbackRecord>("/api/v1/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getFeedbackSummary() {
  return request<FeedbackSummary>("/api/v1/feedback/summary");
}

export function getGraphSchema() {
  return request<GraphSchema>("/api/v1/graph/schema");
}

export function searchGraphNodes(
  label: string,
  searchTerm: string,
  limit = 12,
) {
  const query = new URLSearchParams({
    label,
    q: searchTerm,
    limit: String(limit),
  });
  return request<NodeSearchResponse>(
    `/api/v1/graph/search?${query.toString()}`,
  );
}

export function getSubgraph(
  label: string,
  identity: string,
  depth = 2,
) {
  const query = new URLSearchParams({
    label,
    identity,
    depth: String(depth),
  });
  return request<SubgraphResponse>(
    `/api/v1/graph/subgraph?${query.toString()}`,
  );
}
