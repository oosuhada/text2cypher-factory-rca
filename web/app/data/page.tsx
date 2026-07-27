import {
  ArrowRight,
  CheckCircle2,
  FileSearch,
  GitCompareArrows,
  ShieldCheck,
  Upload,
} from "lucide-react";
import type { Metadata } from "next";

import { PageHeading } from "@/components/page-heading";

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
      <section className="data-status-panel card">
        <div>
          <h2>현재 단계: 검증된 CLI ETL + Streamlit 사전검증</h2>
          <p>
            Next.js의 실제 업로드·승인 작업 관리는 3차 리팩터링에서
            비동기 Worker와 함께 구현합니다. 현재는 임의 파일이 Neo4j
            reader 데이터베이스를 변경하지 못하도록 적재 버튼을 노출하지
            않습니다.
          </p>
        </div>
        <a
          className="secondary-button"
          href="http://localhost:8501"
          target="_blank"
          rel="noreferrer"
        >
          <FileSearch size={16} />
          Data & Health 열기
          <ArrowRight size={15} />
        </a>
      </section>
      <div className="capability-grid">
        {[
          [Upload, "형식 제한", "CiP-DMD JSON·CSV와 10MB 제한"],
          [GitCompareArrows, "멱등 적재", "동일 데이터 재실행 시 카운트 유지"],
          [ShieldCheck, "권한 분리", "loader 완료 후 reader 모드 복귀"],
          [CheckCircle2, "무결성", "노드·관계 수와 고아 레코드 검증"],
        ].map(([Icon, title, body]) => {
          const Component = Icon as typeof Upload;
          return (
            <article className="capability-card subtle-card" key={String(title)}>
              <div>
                <Component size={21} />
              </div>
              <h3>{String(title)}</h3>
              <p>{String(body)}</p>
            </article>
          );
        })}
      </div>
    </div>
  );
}
