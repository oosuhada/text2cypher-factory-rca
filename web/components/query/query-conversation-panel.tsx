"use client";

import {
  AlertTriangle,
  ArrowRight,
  ArrowUp,
  Database,
  LoaderCircle,
  Network,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import type { FormEvent, RefObject } from "react";

import type { Project, ProjectReadiness } from "@/lib/types";
import { ExpertReview } from "@/components/query/expert-review";
import { ResponseNextActions } from "@/components/query/response-next-actions";
import {
  QUERY_PROGRESS,
  QUERY_STATUS_LABEL,
} from "@/components/query/query-config";
import type { QuerySession } from "@/components/query/use-query-session";

type QueryConversationPanelProps = {
  activeProject: Project | null;
  readiness: ProjectReadiness | null;
  projectLoading: boolean;
  projectSwitching: boolean;
  projectContextPending: boolean;
  projectError: string;
  projectRouteError: string;
  queryEnabled: boolean;
  isEquipmentHistory: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  session: QuerySession;
};

export function QueryConversationPanel({
  activeProject,
  readiness,
  projectLoading,
  projectSwitching,
  projectContextPending,
  projectError,
  projectRouteError,
  queryEnabled,
  isEquipmentHistory,
  inputRef,
  session,
}: QueryConversationPanelProps) {
  function submit(event: FormEvent) {
    event.preventDefault();
    void session.runQuestion(session.question);
  }

  return (
    <section className="conversation-panel">
      <div className="workspace-heading">
        <div>
          <span className="eyebrow">Query workspace</span>
          <h1>{activeProject?.name ?? "그래프"}에 질문하세요.</h1>
        </div>
        {session.response && (
          <span className={`result-status status-${session.response.status}`}>
            <span className="status-dot" />
            {QUERY_STATUS_LABEL[session.response.status]}
          </span>
        )}
      </div>

      <div className="conversation-body">
        {(projectLoading ||
          projectSwitching ||
          projectContextPending ||
          (!readiness && !projectError)) && (
          <div className="conversation-empty">
            <LoaderCircle className="spin" size={28} />
            <h2>
              {projectContextPending
                ? "요청한 프로젝트로 전환하고 있습니다."
                : "프로젝트 상태를 확인하고 있습니다."}
            </h2>
          </div>
        )}

        {projectRouteError && (
          <QueryError title="프로젝트를 열 수 없습니다">
            {projectRouteError}
          </QueryError>
        )}
        {projectError && (
          <QueryError title="프로젝트 상태 확인 실패">
            {projectError}
          </QueryError>
        )}

        {readiness && !readiness.can_query && (
          <div className="project-not-ready card">
            <Database size={28} />
            <span className="eyebrow">
              {readiness.lifecycle_status.replaceAll("_", " ")}
            </span>
            <h2>아직 질의할 그래프가 없습니다.</h2>
            <p>
              업로드 {readiness.upload_count}건 · 노드{" "}
              {readiness.node_count}개 · 관계{" "}
              {readiness.relationship_count}개
            </p>
            <p>
              {readiness.next_action === "upload"
                ? "CSV/JSON 파일을 업로드하고 프로파일링하세요."
                : readiness.next_action === "map"
                  ? "업로드한 컬럼을 노드와 관계에 매핑하세요."
                  : "승인된 스키마를 Neo4j에 적재해야 합니다."}
            </p>
            <Link
              className="primary-button"
              href={`${readiness.next_action === "upload" ? "/data" : "/schema"}?project_id=${encodeURIComponent(activeProject?.project_id ?? "")}`}
            >
              {readiness.next_action === "upload"
                ? "Data Pipeline 열기"
                : "Schema Studio 열기"}
              <ArrowRight size={15} />
            </Link>
          </div>
        )}

        {queryEnabled && !session.submittedQuestion && !session.loading && (
          <div className="conversation-empty">
            <span>
              <Network size={30} />
            </span>
            <h2>관계형 질문에서 시작합니다.</h2>
            <p>
              {isEquipmentHistory
                ? "장비별 정비 이력, 비용, 부품 교체와 담당 기술자를 질문해 보세요."
                : "완제품과 구성품의 공정 이력, 품질 실패와 이상 유형, 역방향 영향 범위를 질문해 보세요."}
            </p>
          </div>
        )}

        {session.submittedQuestion && (
          <div className="user-message">
            <span>YOU</span>
            <p>{session.submittedQuestion}</p>
          </div>
        )}

        {session.loading && (
          <div className="agent-progress card">
            <LoaderCircle className="spin" size={19} />
            <div>
              <strong>{QUERY_PROGRESS[session.progressIndex]}</strong>
              <div className="progress-track">
                <span
                  style={{
                    width: `${
                      ((session.progressIndex + 1) / QUERY_PROGRESS.length) *
                      100
                    }%`,
                  }}
                />
              </div>
              <small>
                {session.progressIndex + 1} / {QUERY_PROGRESS.length}
              </small>
            </div>
          </div>
        )}

        {session.error && (
          <QueryError title="API 연결 또는 질의 처리 실패">
            {session.error}
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                void session.runQuestion(session.submittedQuestion)
              }
            >
              <RotateCcw size={15} /> 다시 시도
            </button>
          </QueryError>
        )}

        {session.response && (
          <article className="assistant-answer card">
            <div className="answer-topline">
              <span className="agent-avatar">FG</span>
              <div>
                <strong>FactoryGraph Agent</strong>
                <small>
                  읽기 전용 검증 완료 · {session.response.validation.elapsed_ms}ms
                </small>
              </div>
            </div>
            <p>{session.response.answer}</p>
            {session.response.caveat && (
              <div className="answer-caveat">
                <AlertTriangle size={14} />
                {session.response.caveat}
              </div>
            )}
            <div className="answer-metrics">
              <span>
                <Database size={13} /> 결과 {session.response.row_count}건
              </span>
              <span>
                <Network size={13} />{" "}
                근거 노드 {session.response.evidence.node_count}개
              </span>
              <span>
                <ShieldCheck size={13} />{" "}
                검증 {session.response.validation.attempts}회
              </span>
            </div>
            <ResponseNextActions
              projectId={activeProject?.project_id ?? "cip-dmd"}
              inputRef={inputRef}
              session={session}
            />
            {session.response.status === "success" && (
              <ExpertReview session={session} />
            )}
          </article>
        )}
      </div>

      <form className="query-composer" onSubmit={submit}>
        <textarea
          ref={inputRef}
          value={session.question}
          onChange={(event) => session.setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void session.runQuestion(session.question);
            }
          }}
          placeholder={
            isEquipmentHistory
              ? "예: EQ-PRESS-01의 정비 이력을 보여줘."
              : "예: 완제품 300002의 구성품과 공정 이력을 보여줘."
          }
          rows={2}
          maxLength={2000}
          aria-label="제조 관계 질문"
          disabled={!queryEnabled}
        />
        <div>
          <span>Enter 전송 · Shift + Enter 줄바꿈</span>
          <button
            type="submit"
            aria-label="질문 전송"
            disabled={
              !queryEnabled || session.loading || !session.question.trim()
            }
          >
            {session.loading ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <ArrowUp size={18} />
            )}
          </button>
        </div>
      </form>
    </section>
  );
}

function QueryError({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="query-error">
      <AlertTriangle size={19} />
      <div>
        <strong>{title}</strong>
        <div>{children}</div>
      </div>
    </div>
  );
}
