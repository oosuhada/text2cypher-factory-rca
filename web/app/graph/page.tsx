import type { Metadata } from "next";

import { GraphExplorer } from "@/components/graph-explorer";
import { PageHeading } from "@/components/page-heading";

export const metadata: Metadata = { title: "Graph Explorer" };

export default function GraphPage() {
  return (
    <div className="shell product-page">
      <PageHeading
        eyebrow="Neo4j evidence"
        title="Graph Explorer"
        description="노드 식별자에서 최대 3-hop 관계를 안전하게 펼쳐 실제 적재 경로를 확인합니다."
      />
      <GraphExplorer />
    </div>
  );
}
