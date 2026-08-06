import type { QueryResponse } from "@/lib/types";

export type QueryExample = {
  label: string;
  question: string;
};

export type EvidenceTab = "table" | "graph" | "cypher" | "trace";

const MANUFACTURING_EXAMPLES: QueryExample[] = [
  {
    label: "제품 Genealogy",
    question:
      "완제품 300002의 구성품, 각 구성품의 공정과 품질검사 결과를 보여줘.",
  },
  {
    label: "품질 실패 × 이상",
    question:
      "압력검사에 실패한 완제품과 구성품 공정의 이상 유형을 보여줘.",
  },
  {
    label: "역방향 영향분석",
    question:
      "표면거칠기 검사에 실패한 cylinder bottom이 조립된 완제품을 보여줘.",
  },
  {
    label: "없는 엔티티",
    question:
      "완제품 399999의 구성품과 품질검사 결과를 보여줘.",
  },
];

const EQUIPMENT_EXAMPLES: QueryExample[] = [
  {
    label: "장비 정비 이력",
    question: "EQ-PRESS-01의 정비 이력을 보여줘.",
  },
  {
    label: "고비용 정비",
    question: "비용이 1000달러 이상인 유지보수 이력을 보여줘.",
  },
  {
    label: "부품 교체",
    question: "replacement 유형의 정비 이력과 담당 기술자를 보여줘.",
  },
];

export const QUERY_PROGRESS = [
  "질문 의도 분류",
  "그래프 스키마 주입",
  "Cypher 생성",
  "READ-only 검증",
  "Neo4j 실행",
  "근거 경로 구성",
];

export const QUERY_STATUS_LABEL: Record<QueryResponse["status"], string> = {
  success: "조회 완료",
  empty: "결과 없음",
  blocked: "안전 차단",
  failed: "처리 실패",
  needs_clarification: "조건 확인",
  unsupported: "지원 범위 밖",
};

export function examplesForProject(projectId: string): QueryExample[] {
  if (projectId === "cip-dmd") return MANUFACTURING_EXAMPLES;
  if (projectId === "equipment-history") return EQUIPMENT_EXAMPLES;
  return [];
}
