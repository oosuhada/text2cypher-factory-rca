"use client";

import {
  Activity,
  CheckCircle2,
  CircleDollarSign,
  Gauge,
  LoaderCircle,
  Network,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  getFeedbackSummary,
  getHealth,
  getMetrics,
} from "@/lib/api";
import type {
  FeedbackSummary,
  HealthResponse,
} from "@/lib/types";

type Dashboard = {
  totals?: { nodes?: number; relationships?: number };
  integrity?: Record<string, number>;
  evaluation?: Record<string, string | number | null>;
  runtime?: Record<string, unknown>;
  node_counts?: { label: string; count: number }[];
  relationship_counts?: {
    relationship_type: string;
    count: number;
  }[];
};

function percent(value: unknown) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "—";
}

export function OperationsPanel() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [feedback, setFeedback] = useState<FeedbackSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getHealth(), getMetrics(), getFeedbackSummary()])
      .then(([healthResult, metricResult, feedbackResult]) => {
        setHealth(healthResult);
        setDashboard(metricResult as Dashboard);
        setFeedback(feedbackResult);
      })
      .catch((reason) =>
        setError(
          reason instanceof Error ? reason.message : "운영 지표 조회 실패",
        ),
      );
  }, []);

  if (error) return <div className="inline-error">{error}</div>;
  if (!health || !dashboard || !feedback) {
    return (
      <div className="loading-state">
        <LoaderCircle className="spin" />
        운영 지표를 불러오는 중입니다.
      </div>
    );
  }

  const evaluation = dashboard.evaluation ?? {};
  const runtime = dashboard.runtime ?? {};

  return (
    <div className="operations-content">
      <div className="metric-grid">
        <article className="metric-card card">
          <Network size={19} />
          <span>Graph nodes</span>
          <strong>{dashboard.totals?.nodes?.toLocaleString() ?? "—"}</strong>
          <small>
            관계 {dashboard.totals?.relationships?.toLocaleString() ?? "—"}개
          </small>
        </article>
        <article className="metric-card card">
          <Gauge size={19} />
          <span>Blind accuracy</span>
          <strong>{percent(evaluation.blind_result_accuracy)}</strong>
          <small>Gemini semantic result match</small>
        </article>
        <article className="metric-card card">
          <ShieldCheck size={19} />
          <span>Read-only</span>
          <strong>{percent(evaluation.read_only_compliance_rate)}</strong>
          <small>쓰기 요청 실행 차단</small>
        </article>
        <article className="metric-card card">
          <Activity size={19} />
          <span>Runtime success</span>
          <strong>{percent(runtime.success_rate)}</strong>
          <small>{String(runtime.query_count ?? 0)} audited queries</small>
        </article>
        <article className="metric-card card">
          <UserCheck size={19} />
          <span>Expert reviews</span>
          <strong>{feedback.total_reviews.toLocaleString()}</strong>
          <small>
            {feedback.unique_queries_reviewed.toLocaleString()} unique queries
          </small>
        </article>
      </div>

      <div className="operations-grid">
        <section className="operations-card subtle-card">
          <div className="operations-card-title">
            <CheckCircle2 size={18} />
            <div>
              <h2>Environment checks</h2>
              <p>데이터부터 생성 모델까지 실행 준비 상태</p>
            </div>
          </div>
          <div className="health-list">
            {health.checks.map((check) => (
              <div key={check.check}>
                <span
                  className={
                    check.status === "PASS"
                      ? "status-ready"
                      : "status-degraded"
                  }
                >
                  <span className="status-dot" />
                  {check.status}
                </span>
                <strong>{check.check}</strong>
                <small>{check.detail}</small>
              </div>
            ))}
          </div>
        </section>

        <section className="operations-card subtle-card">
          <div className="operations-card-title">
            <CircleDollarSign size={18} />
            <div>
              <h2>Model runtime</h2>
              <p>로컬 감사로그 기준 누적 사용량</p>
            </div>
          </div>
          <dl className="runtime-list">
            <div>
              <dt>평균 응답시간</dt>
              <dd>{String(runtime.average_elapsed_ms ?? "—")} ms</dd>
            </div>
            <div>
              <dt>모델 호출</dt>
              <dd>{String(runtime.model_call_count ?? 0)}</dd>
            </div>
            <div>
              <dt>입력 토큰</dt>
              <dd>{Number(runtime.input_tokens ?? 0).toLocaleString()}</dd>
            </div>
            <div>
              <dt>추정 비용</dt>
              <dd>${Number(runtime.estimated_cost_usd ?? 0).toFixed(4)}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="distribution-card card">
        <div className="operations-card-title">
          <UserCheck size={18} />
          <div>
            <h2>Domain expert verification</h2>
            <p>append-only 감사기록에 남은 HITL 판정</p>
          </div>
        </div>
        <div className="distribution-grid">
          <div>
            <h3>Decision counts</h3>
            {(
              [
                ["검증 완료", feedback.decision_counts.verified],
                ["추가 확인", feedback.decision_counts.needs_followup],
                ["이견 있음", feedback.decision_counts.disputed],
              ] as const
            ).map(([label, count]) => (
              <div className="distribution-row" key={label}>
                <span>{label}</span>
                <strong>{count.toLocaleString()}</strong>
              </div>
            ))}
          </div>
          <div>
            <h3>Recent reviews</h3>
            {feedback.recent.slice(0, 5).map((review) => (
              <div className="distribution-row" key={review.review_id}>
                <span>
                  {review.reviewer} · {review.decision}
                </span>
                <strong>{review.row_count} rows</strong>
              </div>
            ))}
            {feedback.recent.length === 0 && (
              <p className="local-data-note">
                아직 기록된 전문가 판정이 없습니다.
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="distribution-card card">
        <div className="operations-card-title">
          <Network size={18} />
          <div>
            <h2>Graph distribution</h2>
            <p>현재 Neo4j에 실제 적재된 노드와 관계</p>
          </div>
        </div>
        <div className="distribution-grid">
          <div>
            <h3>Node labels</h3>
            {(dashboard.node_counts ?? []).map((item) => (
              <div className="distribution-row" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.count.toLocaleString()}</strong>
              </div>
            ))}
          </div>
          <div>
            <h3>Relationship types</h3>
            {(dashboard.relationship_counts ?? []).map((item) => (
              <div
                className="distribution-row"
                key={item.relationship_type}
              >
                <span>{item.relationship_type}</span>
                <strong>{item.count.toLocaleString()}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
