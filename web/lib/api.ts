import type {
  GraphSchema,
  HealthResponse,
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

export function getGraphSchema() {
  return request<GraphSchema>("/api/v1/graph/schema");
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
