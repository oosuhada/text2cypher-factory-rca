import type {
  FeedbackDecision,
  FeedbackRecord,
  FeedbackSummary,
  GraphSchema,
  HealthResponse,
  NodeSearchResponse,
  QueryResponse,
  Project,
  ProjectReadiness,
  DatasetProfile,
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

export function queryFactoryGraph(question: string, projectId: string) {
  return request<QueryResponse>("/api/v1/query", {
    method: "POST",
    body: JSON.stringify({ question, project_id: projectId }),
  });
}

export function getProjects() {
  return request<Project[]>("/api/v1/projects");
}

export function createProject(payload: {
  project_id: string;
  name: string;
  domain_type: string;
  dataset_name: string;
}) {
  return request<Project>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function activateProject(projectId: string) {
  return request<Project>(`/api/v1/projects/${projectId}/activate`, {
    method: "POST",
  });
}

export function getProjectReadiness(projectId: string) {
  return request<ProjectReadiness>(
    `/api/v1/projects/${projectId}/readiness`,
  );
}

export function promoteProject(projectId: string) {
  return request<ProjectReadiness>(
    `/api/v1/projects/${projectId}/readiness/promote`,
    { method: "POST" },
  );
}

export function validateNeo4jConnector(
  projectId: string,
  payload: {
    uri: string;
    database: string;
    username: string;
    password_env: string;
  },
) {
  return request<Record<string, unknown>>(
    `/api/v1/projects/${projectId}/connectors/neo4j/validate`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function approveNeo4jConnector(
  projectId: string,
  connectorId: string,
) {
  return request<Record<string, unknown>>(
    `/api/v1/projects/${projectId}/connectors/neo4j/${connectorId}/approve`,
    { method: "POST" },
  );
}

export function profileDataset(
  projectId: string,
  files: { filename: string; content_base64: string }[],
) {
  return request<DatasetProfile>(
    `/api/v1/projects/${projectId}/uploads/profile`,
    {
      method: "POST",
      body: JSON.stringify({ files }),
    },
  );
}

export function getDatasetUploads(projectId: string) {
  return request<{
    project_id: string;
    uploads: DatasetProfile[];
    count: number;
  }>(`/api/v1/projects/${projectId}/uploads`);
}

export function previewGraphMapping(
  projectId: string,
  uploadId: string,
  mapping: Record<string, unknown>,
) {
  return request<Record<string, unknown>>(
    `/api/v1/projects/${projectId}/mappings/preview`,
    {
      method: "POST",
      body: JSON.stringify({
        upload_id: uploadId,
        schema_version: "1.0",
        mapping,
      }),
    },
  );
}

export function approveGraphMapping(
  projectId: string,
  uploadId: string,
  mapping: Record<string, unknown>,
) {
  return request<Record<string, unknown>>(
    `/api/v1/projects/${projectId}/mappings/approve`,
    {
      method: "POST",
      body: JSON.stringify({
        upload_id: uploadId,
        schema_version: "1.0",
        mapping,
      }),
    },
  );
}

export function getApprovedGraphMapping(projectId: string) {
  return request<{
    project_id: string;
    upload_id: string;
    status: string;
    mapping: Record<string, unknown>;
    manifest: Record<string, unknown>;
  }>(`/api/v1/projects/${projectId}/mappings/approved`);
}

export function loadProjectGraph(projectId: string, uploadId: string) {
  return request<Record<string, unknown>>(
    `/api/v1/projects/${projectId}/graph/load`,
    {
      method: "POST",
      body: JSON.stringify({
        upload_id: uploadId,
        confirm_project_id: projectId,
      }),
    },
  );
}

export function getHealth() {
  return request<HealthResponse>("/api/v1/health");
}

export function getMetrics(projectId?: string) {
  const suffix = projectId
    ? `?project_id=${encodeURIComponent(projectId)}`
    : "";
  return request<Record<string, unknown>>(`/api/v1/metrics${suffix}`);
}

export function submitExpertFeedback(payload: {
  project_id: string;
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

export function getFeedbackSummary(projectId?: string) {
  const suffix = projectId
    ? `?project_id=${encodeURIComponent(projectId)}`
    : "";
  return request<FeedbackSummary>(
    `/api/v1/feedback/summary${suffix}`,
  );
}

export function getGraphSchema(projectId?: string) {
  const suffix = projectId
    ? `?project_id=${encodeURIComponent(projectId)}`
    : "";
  return request<GraphSchema>(`/api/v1/graph/schema${suffix}`);
}

export function searchGraphNodes(
  label: string,
  searchTerm: string,
  limit = 12,
  projectId?: string,
) {
  const query = new URLSearchParams({
    label,
    q: searchTerm,
    limit: String(limit),
  });
  if (projectId) query.set("project_id", projectId);
  return request<NodeSearchResponse>(
    `/api/v1/graph/search?${query.toString()}`,
  );
}

export function getSubgraph(
  label: string,
  identity: string,
  depth = 2,
  projectId?: string,
) {
  const query = new URLSearchParams({
    label,
    identity,
    depth: String(depth),
  });
  if (projectId) query.set("project_id", projectId);
  return request<SubgraphResponse>(
    `/api/v1/graph/subgraph?${query.toString()}`,
  );
}
