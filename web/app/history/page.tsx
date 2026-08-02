import type { Metadata } from "next";

import { HistoryList } from "@/components/history-list";
import { PageHeading } from "@/components/page-heading";

export const metadata: Metadata = { title: "History" };

export default function HistoryPage() {
  return (
    <div className="shell product-page">
      <PageHeading
        eyebrow="Device history"
        title="최근 조사 기록"
        description="질문과 답변, 실행 Cypher와 근거 그래프를 이 브라우저에서 다시 확인합니다."
      />
      <HistoryList />
    </div>
  );
}
