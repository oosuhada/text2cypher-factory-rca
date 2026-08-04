import type { Metadata } from "next";

import { PageHeading } from "@/components/page-heading";
import { SchemaStudio } from "@/components/schema-studio";

export const metadata: Metadata = { title: "Schema Studio" };

export default function SchemaPage() {
  return (
    <div className="shell product-page">
      <PageHeading
        eyebrow="Dataset to graph"
        title="Schema Studio"
        description="원본 컬럼을 노드·속성·관계로 매핑하고 예상 규모를 검토한 뒤 프로젝트 그래프에 적재합니다."
      />
      <SchemaStudio />
    </div>
  );
}
