"use client";

import {
  Check,
  Clipboard,
  Code2,
  Network,
  ShieldCheck,
  Table2,
} from "lucide-react";

import { EvidenceGraph } from "@/components/evidence-graph";
import { ResultTable } from "@/components/result-table";
import type { EvidenceTab } from "@/components/query/query-config";
import type { QuerySession } from "@/components/query/use-query-session";

const EVIDENCE_TABS = [
  { id: "table" as const, label: "결과", icon: Table2 },
  { id: "graph" as const, label: "그래프", icon: Network },
  { id: "cypher" as const, label: "Cypher", icon: Code2 },
  { id: "trace" as const, label: "검증", icon: ShieldCheck },
];

export function QueryEvidencePanel({ session }: { session: QuerySession }) {
  const response = session.response;
  return (
    <aside className="evidence-panel" id="query-evidence">
      <div className="evidence-heading">
        <div>
          <strong>Evidence</strong>
          <span>답변과 동일한 조회의 근거·검증 기록</span>
        </div>
        {response && <span className="mono">{response.row_count} rows</span>}
      </div>

      {!response ? (
        <div className="evidence-empty">
          <Network size={27} />
          <p>질문을 실행하면 Cypher, 결과표, 관계 경로가 표시됩니다.</p>
        </div>
      ) : (
        <>
          <div className="evidence-tabs" role="tablist">
            {EVIDENCE_TABS.map((tab) => (
              <button
                type="button"
                role="tab"
                aria-selected={session.activeTab === tab.id}
                className={session.activeTab === tab.id ? "active" : ""}
                key={tab.id}
                onClick={() => session.setActiveTab(tab.id)}
              >
                <tab.icon size={14} />
                {tab.label}
              </button>
            ))}
          </div>
          <EvidenceContent
            activeTab={session.activeTab}
            session={session}
          />
        </>
      )}
    </aside>
  );
}

function EvidenceContent({
  activeTab,
  session,
}: {
  activeTab: EvidenceTab;
  session: QuerySession;
}) {
  const response = session.response;
  if (!response) return null;
  return (
    <div className="evidence-content">
      {activeTab === "table" && <ResultTable rows={response.rows} />}
      {activeTab === "graph" && (
        <>
          <EvidenceGraph evidence={response.evidence} />
          <p className="graph-caption">
            노드 {response.evidence.node_count} · 관계{" "}
            {response.evidence.relationship_count} · 드래그/스크롤로 탐색
          </p>
        </>
      )}
      {activeTab === "cypher" && (
        <div className="cypher-panel">
          <button type="button" onClick={() => void session.copyCypher()}>
            {session.copied ? <Check size={14} /> : <Clipboard size={14} />}
            {session.copied ? "복사됨" : "복사"}
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
  );
}
