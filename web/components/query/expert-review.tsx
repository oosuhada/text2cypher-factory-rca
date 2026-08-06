"use client";

import { AlertTriangle, CheckCircle2, Siren, UserCheck } from "lucide-react";

import type { FeedbackDecision } from "@/lib/types";
import type { QuerySession } from "@/components/query/use-query-session";

type ExpertReviewProps = {
  session: QuerySession;
};

export function ExpertReview({ session }: ExpertReviewProps) {
  return (
    <details className="expert-review">
      <summary className="expert-review-heading">
        <UserCheck size={17} />
        <div>
          <strong>도메인 전문가 검증</strong>
          <span>전문가 전용 · 판정은 별도 감사기록으로 남습니다.</span>
        </div>
      </summary>
      <div className="expert-review-body">
        {session.reviewDecision ? (
          <div className="review-saved">
            <CheckCircle2 size={16} />
            {session.reviewDecision === "verified"
              ? "검증 완료"
              : session.reviewDecision === "disputed"
                ? "이견 있음"
                : "추가 확인 필요"}{" "}
            판정을 기록했습니다.
          </div>
        ) : (
          <>
            <div className="review-fields">
              <input
                value={session.reviewer}
                onChange={(event) => session.setReviewer(event.target.value)}
                placeholder="검토자 표시"
                maxLength={120}
                aria-label="검토자 표시"
              />
              <textarea
                value={session.reviewNote}
                onChange={(event) => session.setReviewNote(event.target.value)}
                placeholder="판정 근거 또는 추가 확인 사항"
                maxLength={2000}
                rows={2}
                aria-label="전문가 검토 의견"
              />
            </div>
            <div className="review-actions">
              <ReviewButton
                decision="verified"
                disabled={session.reviewLoading}
                onSubmit={session.submitReview}
              />
              <ReviewButton
                decision="needs_followup"
                disabled={session.reviewLoading}
                onSubmit={session.submitReview}
              />
              <ReviewButton
                decision="disputed"
                disabled={session.reviewLoading}
                onSubmit={session.submitReview}
              />
            </div>
          </>
        )}
        {session.reviewError && (
          <div className="review-error">{session.reviewError}</div>
        )}
      </div>
    </details>
  );
}

function ReviewButton({
  decision,
  disabled,
  onSubmit,
}: {
  decision: FeedbackDecision;
  disabled: boolean;
  onSubmit: (decision: FeedbackDecision) => Promise<void>;
}) {
  const presentation = {
    verified: { icon: CheckCircle2, label: "검증 완료" },
    needs_followup: { icon: Siren, label: "추가 확인" },
    disputed: { icon: AlertTriangle, label: "이견 있음" },
  }[decision];
  const Icon = presentation.icon;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => void onSubmit(decision)}
    >
      <Icon size={14} /> {presentation.label}
    </button>
  );
}
