import type { Metadata } from "next";

import { OperationsPanel } from "@/components/operations-panel";
import { PageHeading } from "@/components/page-heading";

export const metadata: Metadata = { title: "Operations" };

export default function OperationsPage() {
  return (
    <div className="shell product-page">
      <PageHeading
        eyebrow="System observability"
        title="Operations"
        description="그래프 무결성, 모델 평가, 읽기 전용 준수와 런타임 사용량을 실제 서비스 데이터로 확인합니다."
      />
      <OperationsPanel />
    </div>
  );
}
