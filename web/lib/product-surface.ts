export const PRODUCT_NAVIGATION = [
  { href: "/projects", label: "Projects", icon: "projects" },
  { href: "/query", label: "Query Studio", icon: "query" },
  { href: "/graph", label: "Evidence / Graph", icon: "graph" },
  { href: "/history", label: "History", icon: "history" },
] as const;

export const INTERNAL_CONSOLE_URL =
  process.env.NEXT_PUBLIC_INTERNAL_CONSOLE_URL ?? "http://localhost:8501";

const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: "초안",
  profiling: "프로파일링",
  mapping_review: "매핑 검토",
  loading: "적재 중",
  validating: "무결성 검증",
  evaluation_required: "평가 필요",
  ready: "질의 가능",
  failed: "조치 필요",
  archived: "보관됨",
};

const NEXT_ACTION_LABELS: Record<string, string> = {
  upload: "데이터 등록 필요",
  connect: "데이터 연결 필요",
  map: "매핑 검토 필요",
  load: "그래프 적재 필요",
  validate: "무결성 확인 필요",
  evaluate: "평가 필요",
  activate: "프로젝트 활성화 필요",
  query: "질의 가능",
};

export function projectStatusLabel(status: string) {
  return PROJECT_STATUS_LABELS[status] ?? status;
}

export function readinessStatusLabel(readiness?: {
  can_query: boolean;
  next_action: string;
  node_count: number;
}) {
  if (!readiness) return "상태 확인 중";
  if (readiness.can_query) {
    return `질의 가능 · ${readiness.node_count.toLocaleString()} nodes`;
  }
  return NEXT_ACTION_LABELS[readiness.next_action] ?? "상태 확인 필요";
}

export function internalConsoleUrl(
  workspace: string,
  projectId?: string,
) {
  const url = new URL(INTERNAL_CONSOLE_URL);
  url.searchParams.set("workspace", workspace);
  if (projectId) url.searchParams.set("project_id", projectId);
  return url.toString();
}

export const SURFACE_OWNERSHIP = {
  projectSelection: "react",
  rcaQuery: "react",
  evidenceGraph: "react",
  conversationHistory: "react",
  expertReview: "react",
  dataSources: "streamlit",
  pipeline: "streamlit",
  evaluations: "streamlit",
  auditLogs: "streamlit",
  modelDiagnostics: "streamlit",
  platformState: "backend",
} as const;
