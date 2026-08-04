"use client";

import {
  AlertTriangle,
  ArrowUp,
  Check,
  CheckCircle2,
  Clipboard,
  Clock3,
  Code2,
  Database,
  GitBranch,
  LoaderCircle,
  MessageSquareText,
  Network,
  RotateCcw,
  ShieldCheck,
  Siren,
  Table2,
  UserCheck,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { EvidenceGraph } from "@/components/evidence-graph";
import { ResultTable } from "@/components/result-table";
import {
  queryFactoryGraph,
  submitExpertFeedback,
} from "@/lib/api";
import { readHistory, saveConversation } from "@/lib/history";
import type {
  FeedbackDecision,
  QueryResponse,
  StoredConversation,
} from "@/lib/types";
import { useProject } from "@/components/project-context";

const EXAMPLES = [
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

const EQUIPMENT_EXAMPLES = [
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

const PROGRESS = [
  "질문 의도 분류",
  "그래프 스키마 주입",
  "Cypher 생성",
  "READ-only 검증",
  "Neo4j 실행",
  "근거 경로 구성",
];

const STATUS_LABEL: Record<QueryResponse["status"], string> = {
  success: "조회 완료",
  empty: "결과 없음",
  blocked: "안전 차단",
  failed: "처리 실패",
  needs_clarification: "조건 확인",
  unsupported: "지원 범위 밖",
};

type EvidenceTab = "table" | "graph" | "cypher" | "trace";

export function QueryWorkspace() {
  const {
    activeProject,
    readiness,
    loading: projectLoading,
    error: projectError,
  } = useProject();
  const projectId = activeProject?.project_id ?? "cip-dmd";
  const isEquipmentHistory = projectId === "equipment-history";
  const examples =
    projectId === "cip-dmd"
      ? EXAMPLES
      : isEquipmentHistory
        ? EQUIPMENT_EXAMPLES
        : [];
  const queryEnabled = Boolean(readiness?.can_query);
  const searchParams = useSearchParams();
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [history, setHistory] = useState<StoredConversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [progressIndex, setProgressIndex] = useState(0);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<EvidenceTab>("table");
  const [copied, setCopied] = useState(false);
  const [reviewer, setReviewer] = useState("domain-expert");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewDecision, setReviewDecision] =
    useState<FeedbackDecision | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const stored = readHistory(projectId);
      setHistory(stored);
      setQuestion("");
      setSubmittedQuestion("");
      setResponse(null);
      setError("");
      setReviewDecision(null);
      setReviewNote("");
      setReviewError("");
      const conversationId = searchParams.get("conversation");
      const selected = stored.find((item) => item.id === conversationId);
      if (selected) {
        setQuestion(selected.question);
        setSubmittedQuestion(selected.question);
        setResponse(selected.response);
        setReviewDecision(null);
        setReviewNote("");
        setReviewError("");
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [searchParams, projectId]);

  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(
      () =>
        setProgressIndex((index) =>
          Math.min(index + 1, PROGRESS.length - 1),
        ),
      650,
    );
    return () => window.clearInterval(timer);
  }, [loading]);

  const evidenceTabs = useMemo(
    () => [
      { id: "table" as const, label: "결과", icon: Table2 },
      { id: "graph" as const, label: "그래프", icon: Network },
      { id: "cypher" as const, label: "Cypher", icon: Code2 },
      { id: "trace" as const, label: "검증", icon: ShieldCheck },
    ],
    [],
  );

  const runQuestion = async (input: string) => {
    const normalized = input.trim();
    if (!normalized || loading) return;
    setLoading(true);
    setProgressIndex(0);
    setError("");
    setResponse(null);
    setReviewDecision(null);
    setReviewNote("");
    setReviewError("");
    setSubmittedQuestion(normalized);
    try {
      const result = await queryFactoryGraph(normalized, projectId);
      setResponse(result);
      setActiveTab(result.evidence.nodes.length > 0 ? "graph" : "table");
      const now = new Date().toISOString();
      const item: StoredConversation = {
        id: crypto.randomUUID(),
        title:
          normalized.length > 38
            ? `${normalized.slice(0, 37)}…`
            : normalized,
        createdAt: now,
        updatedAt: now,
        question: normalized,
        response: result,
        projectId,
      };
      setHistory(saveConversation(item, projectId));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "질의를 처리하지 못했습니다.",
      );
    } finally {
      setLoading(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void runQuestion(question);
  };

  const copyCypher = async () => {
    if (!response?.cypher) return;
    await navigator.clipboard.writeText(response.cypher);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  const submitReview = async (decision: FeedbackDecision) => {
    if (!response || reviewLoading) return;
    setReviewLoading(true);
    setReviewError("");
    try {
      await submitExpertFeedback({
        project_id: projectId,
        question: response.question,
        cypher: response.cypher,
        query_status: response.status,
        provider: response.provider,
        row_count: response.row_count,
        decision,
        reviewer: reviewer.trim() || "domain-expert",
        note: reviewNote.trim(),
      });
      setReviewDecision(decision);
    } catch (reason) {
      setReviewError(
        reason instanceof Error ? reason.message : "검증 기록 저장 실패",
      );
    } finally {
      setReviewLoading(false);
    }
  };

  return (
    <div className="workspace-shell">
      <aside className="workspace-sidebar">
        <div className="workspace-sidebar-title">
          <MessageSquareText size={17} />
          <div>
            <strong>Investigation</strong>
            <span>Natural language → graph</span>
          </div>
        </div>

        <section>
          <p className="workspace-label">Demo questions</p>
          <div className="example-list">
            {examples.map((example) => (
              <button
                type="button"
                key={example.label}
                disabled={!queryEnabled}
                onClick={() => {
                  setQuestion(example.question);
                  void runQuestion(example.question);
                }}
              >
                <GitBranch size={14} />
                <span>
                  <strong>{example.label}</strong>
                  <small>{example.question}</small>
                </span>
              </button>
            ))}
            {!examples.length && (
              <p className="workspace-hint">
                이 프로젝트의 검증 질문은 데이터 적재 후 등록할 수 있습니다.
              </p>
            )}
          </div>
        </section>

        <section className="recent-section">
          <div className="workspace-label-row">
            <p className="workspace-label">Recent</p>
            <Link href="/history">전체</Link>
          </div>
          {history.slice(0, 5).map((item) => (
            <button
              type="button"
              key={item.id}
              className="recent-item"
              onClick={() => {
                setQuestion(item.question);
                setSubmittedQuestion(item.question);
                setResponse(item.response);
                setReviewDecision(null);
                setReviewNote("");
                setReviewError("");
              }}
            >
              <Clock3 size={13} />
              <span>{item.title}</span>
            </button>
          ))}
          {history.length === 0 && (
            <p className="workspace-hint">첫 질문을 실행하면 이 기기에 저장됩니다.</p>
          )}
        </section>

        <div className="workspace-safety">
          <ShieldCheck size={17} />
          <div>
            <strong>Reader mode</strong>
            <span>CREATE · DELETE · SET 차단</span>
          </div>
        </div>
      </aside>

      <section className="conversation-panel">
        <div className="workspace-heading">
          <div>
            <span className="eyebrow">Query workspace</span>
            <h1>{activeProject?.name ?? "그래프"}에 질문하세요.</h1>
          </div>
          {response && (
            <span className={`result-status status-${response.status}`}>
              <span className="status-dot" />
              {STATUS_LABEL[response.status]}
            </span>
          )}
        </div>

        <div className="conversation-body">
          {(projectLoading || (!readiness && !projectError)) && (
            <div className="conversation-empty">
              <LoaderCircle className="spin" size={28} />
              <h2>프로젝트 상태를 확인하고 있습니다.</h2>
            </div>
          )}

          {projectError && (
            <div className="query-error">
              <AlertTriangle size={19} />
              <div>
                <strong>프로젝트 상태 확인 실패</strong>
                <p>{projectError}</p>
              </div>
            </div>
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
                href={
                  readiness.next_action === "upload" ? "/data" : "/schema"
                }
              >
                {readiness.next_action === "upload"
                  ? "Data Pipeline 열기"
                  : "Schema Studio 열기"}
              </Link>
            </div>
          )}

          {queryEnabled && !submittedQuestion && !loading && (
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

          {submittedQuestion && (
            <div className="user-message">
              <span>YOU</span>
              <p>{submittedQuestion}</p>
            </div>
          )}

          {loading && (
            <div className="agent-progress card">
              <LoaderCircle className="spin" size={19} />
              <div>
                <strong>{PROGRESS[progressIndex]}</strong>
                <div className="progress-track">
                  <span
                    style={{
                      width: `${((progressIndex + 1) / PROGRESS.length) * 100}%`,
                    }}
                  />
                </div>
                <small>
                  {progressIndex + 1} / {PROGRESS.length}
                </small>
              </div>
            </div>
          )}

          {error && (
            <div className="query-error">
              <AlertTriangle size={19} />
              <div>
                <strong>API 연결 또는 질의 처리 실패</strong>
                <p>{error}</p>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void runQuestion(question)}
                >
                  <RotateCcw size={15} /> 다시 시도
                </button>
              </div>
            </div>
          )}

          {response && (
            <article className="assistant-answer card">
              <div className="answer-topline">
                <span className="agent-avatar">FG</span>
                <div>
                  <strong>FactoryGraph Agent</strong>
                  <small>
                    {response.provider} · {response.validation.elapsed_ms}ms
                  </small>
                </div>
              </div>
              <p>{response.answer}</p>
              {response.caveat && (
                <div className="answer-caveat">
                  <AlertTriangle size={14} />
                  {response.caveat}
                </div>
              )}
              <div className="answer-metrics">
                <span>
                  <Database size={13} /> {response.row_count} rows
                </span>
                <span>
                  <Network size={13} /> {response.evidence.node_count} nodes
                </span>
                <span>
                  <ShieldCheck size={13} />{" "}
                  {response.validation.attempts} validation
                </span>
              </div>
              <div className="expert-review">
                <div className="expert-review-heading">
                  <UserCheck size={17} />
                  <div>
                    <strong>도메인 전문가 검증</strong>
                    <span>
                      판정은 답변을 바꾸지 않고 별도 감사기록으로 남습니다.
                    </span>
                  </div>
                </div>
                {reviewDecision ? (
                  <div className="review-saved">
                    <CheckCircle2 size={16} />
                    {reviewDecision === "verified"
                      ? "검증 완료"
                      : reviewDecision === "disputed"
                        ? "이견 있음"
                        : "추가 확인 필요"}{" "}
                    판정을 기록했습니다.
                  </div>
                ) : (
                  <>
                    <div className="review-fields">
                      <input
                        value={reviewer}
                        onChange={(event) => setReviewer(event.target.value)}
                        placeholder="검토자 표시"
                        maxLength={120}
                        aria-label="검토자 표시"
                      />
                      <textarea
                        value={reviewNote}
                        onChange={(event) => setReviewNote(event.target.value)}
                        placeholder="판정 근거 또는 추가 확인 사항"
                        maxLength={2000}
                        rows={2}
                        aria-label="전문가 검토 의견"
                      />
                    </div>
                    <div className="review-actions">
                      <button
                        type="button"
                        disabled={reviewLoading}
                        onClick={() => void submitReview("verified")}
                      >
                        <CheckCircle2 size={14} /> 검증 완료
                      </button>
                      <button
                        type="button"
                        disabled={reviewLoading}
                        onClick={() => void submitReview("needs_followup")}
                      >
                        <Siren size={14} /> 추가 확인
                      </button>
                      <button
                        type="button"
                        disabled={reviewLoading}
                        onClick={() => void submitReview("disputed")}
                      >
                        <AlertTriangle size={14} /> 이견 있음
                      </button>
                    </div>
                  </>
                )}
                {reviewError && (
                  <div className="review-error">{reviewError}</div>
                )}
              </div>
            </article>
          )}
        </div>

        <form className="query-composer" onSubmit={submit}>
          <textarea
            ref={inputRef}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void runQuestion(question);
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
                !queryEnabled || loading || !question.trim()
              }
            >
              {loading ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <ArrowUp size={18} />
              )}
            </button>
          </div>
        </form>
      </section>

      <aside className="evidence-panel">
        <div className="evidence-heading">
          <div>
            <strong>Evidence</strong>
            <span>조회 근거와 검증 기록</span>
          </div>
          {response && (
            <span className="mono">{response.row_count} rows</span>
          )}
        </div>

        {!response ? (
          <div className="evidence-empty">
            <Network size={27} />
            <p>질문을 실행하면 Cypher, 결과표, 관계 경로가 표시됩니다.</p>
          </div>
        ) : (
          <>
            <div className="evidence-tabs" role="tablist">
              {evidenceTabs.map((tab) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  className={activeTab === tab.id ? "active" : ""}
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <tab.icon size={14} />
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="evidence-content">
              {activeTab === "table" && (
                <ResultTable rows={response.rows} />
              )}
              {activeTab === "graph" && (
                <>
                  <EvidenceGraph evidence={response.evidence} />
                  <p className="graph-caption">
                    노드 {response.evidence.node_count} · 관계{" "}
                    {response.evidence.relationship_count} · 드래그/스크롤로
                    탐색
                  </p>
                </>
              )}
              {activeTab === "cypher" && (
                <div className="cypher-panel">
                  <button type="button" onClick={copyCypher}>
                    {copied ? <Check size={14} /> : <Clipboard size={14} />}
                    {copied ? "복사됨" : "복사"}
                  </button>
                  <pre>
                    <code>{response.cypher || "실행된 Cypher가 없습니다."}</code>
                  </pre>
                </div>
              )}
              {activeTab === "trace" && (
                <div className="trace-panel">
                  <div className="trace-summary">
                    <ShieldCheck size={19} />
                    <div>
                      <strong>검증 {response.validation.attempts}회</strong>
                      <span>
                        오류 {response.validation.errors.length}건 ·{" "}
                        {response.validation.elapsed_ms}ms
                      </span>
                    </div>
                  </div>
                  {response.validation.trace.map((step, index) => (
                    <div className="trace-row" key={index}>
                      <span>{index + 1}</span>
                      <code>
                        {String(step.step ?? step.status ?? "validation")}
                      </code>
                    </div>
                  ))}
                  {response.validation.trace.length === 0 && (
                    <p className="workspace-hint">
                      상세 trace가 없는 단일 검증 경로입니다.
                    </p>
                  )}
                  {response.validation.errors.map((message) => (
                    <div className="trace-error" key={message}>
                      {message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
