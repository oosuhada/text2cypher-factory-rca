"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { RefObject } from "react";

import type { QuerySession } from "@/components/query/use-query-session";

export function ResponseNextActions({
  projectId,
  inputRef,
  session,
}: {
  projectId: string;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  session: QuerySession;
}) {
  const response = session.response;
  if (!response) return null;

  function continueQuestion(value = session.submittedQuestion) {
    session.prepareFollowUp(value);
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }

  if (response.status === "success") {
    return (
      <div className="answer-next-actions" aria-label="조회 결과 다음 행동">
        <a className="evidence-jump" href="#query-evidence">
          결과와 관계 근거 확인 <ArrowRight size={14} />
        </a>
        <Link
          className="secondary-button"
          href={`/history?project_id=${encodeURIComponent(projectId)}`}
        >
          저장된 기록 보기 <ArrowRight size={14} />
        </Link>
      </div>
    );
  }

  const guidance = {
    empty: {
      title: "일치하는 관계를 찾지 못했습니다.",
      detail: "식별자, 공정명, 검사 조건 또는 기간을 바꿔 다시 질문해 보세요.",
      action: "조건 바꿔 다시 질문",
    },
    blocked: {
      title: "조회 전용 서비스에서 변경 요청을 차단했습니다.",
      detail: "삭제·수정 대신 영향 범위나 현재 상태를 조회하는 질문으로 바꿔 주세요.",
      action: "안전한 조회 질문 작성",
    },
    needs_clarification: {
      title: "질문 조건을 조금 더 구체화해야 합니다.",
      detail: "설비·제품·부품 식별자와 확인하려는 공정 또는 검사 조건을 추가해 주세요.",
      action: "조건 추가하기",
    },
    unsupported: {
      title: "현재 그래프가 지원하는 RCA 범위를 벗어났습니다.",
      detail: "제품 genealogy, 공정 이력, 품질 실패, 이상 유형 또는 영향 범위를 질문해 주세요.",
      action: "지원 질문으로 바꾸기",
    },
    failed: {
      title: "질의를 완료하지 못했습니다.",
      detail: "잠시 후 다시 실행하거나 질문 조건을 단순화해 주세요.",
      action: "질문 다시 준비",
    },
  }[response.status];

  return (
    <div className={`response-guidance guidance-${response.status}`}>
      <strong>{guidance.title}</strong>
      <p>{guidance.detail}</p>
      <button
        type="button"
        className="secondary-button"
        onClick={() => continueQuestion()}
      >
        {guidance.action}
      </button>
      {(response.cypher || response.validation.trace.length > 0) && (
        <a className="evidence-jump" href="#query-evidence">
          실행·검증 상세 보기 <ArrowRight size={14} />
        </a>
      )}
    </div>
  );
}
