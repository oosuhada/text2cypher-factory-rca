"use client";

import { Clock3, GitBranch, MessageSquareText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { RefObject } from "react";

import type { StoredConversation } from "@/lib/types";
import type { QueryExample } from "@/components/query/query-config";

type QuerySidebarProps = {
  examples: QueryExample[];
  history: StoredConversation[];
  queryEnabled: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  onPreviewQuestion: (question: string) => void;
  onOpenConversation: (item: StoredConversation) => void;
};

export function QuerySidebar({
  examples,
  history,
  queryEnabled,
  inputRef,
  onPreviewQuestion,
  onOpenConversation,
}: QuerySidebarProps) {
  return (
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
                onPreviewQuestion(example.question);
                inputRef.current?.focus();
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
            onClick={() => onOpenConversation(item)}
          >
            <Clock3 size={13} />
            <span>{item.title}</span>
          </button>
        ))}
        {history.length === 0 && (
          <p className="workspace-hint">
            첫 질문을 실행하면 이 기기에 저장됩니다.
          </p>
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
  );
}
