"use client";

import { ArrowRight, Clock3, History, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { clearHistory, readHistory, removeConversation } from "@/lib/history";
import type { StoredConversation } from "@/lib/types";
import { QUERY_STATUS_LABEL } from "@/components/query/query-config";
import { useProject } from "@/components/project-context";

export function HistoryList() {
  const { activeProject } = useProject();
  const projectId = activeProject?.project_id ?? "cip-dmd";
  const [items, setItems] = useState<StoredConversation[]>([]);

  useEffect(() => {
    const timer = window.setTimeout(
      () => setItems(readHistory(projectId)),
      0,
    );
    return () => window.clearTimeout(timer);
  }, [projectId]);

  if (items.length === 0) {
    return (
      <div className="empty-state card">
        <span>
          <History size={30} />
        </span>
        <h2>아직 저장된 대화가 없습니다.</h2>
        <p>Query Studio에서 질문을 실행하면 이 기기에 최근 20개가 저장됩니다.</p>
        <Link
          href={`/query?project_id=${encodeURIComponent(projectId)}`}
          className="primary-button"
        >
          첫 질문 시작 <ArrowRight size={16} />
        </Link>
      </div>
    );
  }

  return (
    <div className="history-list">
      <div className="history-toolbar">
        <span>이 기기에 저장된 대화 {items.length}개</span>
        <button
          type="button"
          className="ghost-button"
          onClick={() => {
            clearHistory(projectId);
            setItems([]);
          }}
        >
          <Trash2 size={14} /> 모두 지우기
        </button>
      </div>
      {items.map((item) => (
        <article className="history-card subtle-card" key={item.id}>
          <div className="history-meta">
            <span className={`status-${item.response.status}`}>
              <span className="status-dot" />
              {QUERY_STATUS_LABEL[item.response.status]}
            </span>
            <time>
              <Clock3 size={13} />
              {new Date(item.updatedAt).toLocaleString("ko-KR")}
            </time>
          </div>
          <h2>{item.title}</h2>
          <p>{item.response.answer}</p>
          <div className="history-stats">
            <span>결과 {item.response.row_count}건</span>
            <span>근거 노드 {item.response.evidence.node_count}개</span>
            <span>검증 {item.response.validation.attempts}회</span>
          </div>
          <div className="history-actions">
            <Link
              href={`/query?project_id=${encodeURIComponent(projectId)}&conversation=${encodeURIComponent(item.id)}`}
              className="secondary-button"
            >
              다시 열기 <ArrowRight size={14} />
            </Link>
            <button
              type="button"
              className="ghost-button"
              aria-label={`${item.title} 삭제`}
              onClick={() => setItems(removeConversation(item.id, projectId))}
            >
              <Trash2 size={14} />
            </button>
          </div>
        </article>
      ))}
      <p className="local-data-note">
        최근 RCA 기록은 현재 브라우저에 프로젝트별로 저장됩니다.
      </p>
    </div>
  );
}
