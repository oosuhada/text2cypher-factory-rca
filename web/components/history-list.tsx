"use client";

import { ArrowRight, Clock3, History, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { clearHistory, readHistory, removeConversation } from "@/lib/history";
import type { StoredConversation } from "@/lib/types";
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
              {item.response.status}
            </span>
            <time>
              <Clock3 size={13} />
              {new Date(item.updatedAt).toLocaleString("ko-KR")}
            </time>
          </div>
          <h2>{item.title}</h2>
          <p>{item.response.answer}</p>
          <div className="history-stats">
            <span>{item.response.row_count} rows</span>
            <span>{item.response.evidence.node_count} nodes</span>
            <span>{item.response.provider}</span>
          </div>
          <div className="history-actions">
            <Link
              href={`/query?conversation=${encodeURIComponent(item.id)}`}
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
        현재 기록은 브라우저 로컬 저장소에만 보관됩니다. 사용자 계정과
        서버 동기화는 다음 리팩터링 단계에서 추가합니다.
      </p>
    </div>
  );
}
