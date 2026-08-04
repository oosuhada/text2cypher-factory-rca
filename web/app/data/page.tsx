import type { Metadata } from "next";

import { PageHeading } from "@/components/page-heading";
import { DataOnboarding } from "@/components/data-onboarding";

export const metadata: Metadata = { title: "Data Pipeline" };

const STEPS = [
  ["01", "Upload", "JSON·CSV 원본을 격리 영역에 등록"],
  ["02", "Profile", "스키마와 공통 ID를 메모리에서 분석"],
  ["03", "Dry-run", "노드·관계 예상치와 격리 행 검증"],
  ["04", "Approve", "관리자가 변경 범위와 무결성 확인"],
  ["05", "Load", "loader 권한으로 적재 후 reader로 복귀"],
];

export default function DataPage() {
  return (
    <div className="shell product-page">
      <PageHeading
        eyebrow="Controlled ingestion"
        title="Data Pipeline"
        description="사용자 파일을 운영 그래프에 바로 쓰지 않고 검증·승인·무결성 단계를 통과시킵니다."
      />
      <div className="data-pipeline">
        {STEPS.map(([number, title, body]) => (
          <article className="data-step subtle-card" key={number}>
            <span>{number}</span>
            <h2>{title}</h2>
            <p>{body}</p>
          </article>
        ))}
      </div>
      <DataOnboarding />
    </div>
  );
}
