import {
  ArrowRight,
  CheckCircle2,
  Database,
  FileCode2,
  GitBranch,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

import { ProjectOverview } from "@/components/project-overview";

import "./landing.css";

const CAPABILITIES = [
  {
    icon: Network,
    number: "01",
    title: "관계를 먼저 구조화",
    body: "완제품·구성품·공정·장비·이상·품질을 6개 노드와 7개 관계로 연결합니다.",
  },
  {
    icon: FileCode2,
    number: "02",
    title: "질문을 Cypher로",
    body: "자연어를 그래프 질의로 변환하고 스키마·문법·도메인 값을 실행 전에 검사합니다.",
  },
  {
    icon: ShieldCheck,
    number: "03",
    title: "쓰기 요청은 차단",
    body: "읽기 전용 계정과 다중 검증으로 변경 쿼리를 실행 경로에서 제거합니다.",
  },
  {
    icon: GitBranch,
    number: "04",
    title: "근거 경로까지 전달",
    body: "답변만 보여주지 않고 결과표·실행 Cypher·실제 Neo4j 관계를 함께 제공합니다.",
  },
];

const PIPELINE = [
  ["Ask", "현업 언어로 관계 질문"],
  ["Generate", "스키마 기반 Cypher 생성"],
  ["Verify", "READ-only·EXPLAIN·의미 검사"],
  ["Trace", "조회값과 그래프 근거 확인"],
];

export default function HomePage() {
  return (
    <>
      <section className="landing-hero">
        <div className="shell hero-grid">
          <div className="hero-copy">
            <span className="eyebrow">Manufacturing knowledge graph</span>
            <h1 className="display-title">
              Find the path.
              <span>Keep the proof.</span>
            </h1>
            <p className="lede">
              제조 관계를 자연어로 묻고, 검증된 Cypher와 실제 그래프
              경로로 RCA 후보를 확인합니다. 추정한 답변이 아니라 조회한
              근거를 남깁니다.
            </p>
            <div className="hero-actions">
              <Link href="/query" className="primary-button">
                RCA 질문 시작
                <ArrowRight size={17} />
              </Link>
              <Link href="/graph" className="secondary-button">
                그래프 탐색
                <Network size={17} />
              </Link>
            </div>
            <div className="hero-proof">
              <span>
                <CheckCircle2 size={15} /> 읽기 전용 검증
              </span>
              <span>
                <CheckCircle2 size={15} /> 결과표·관계 근거
              </span>
              <span>
                <CheckCircle2 size={15} /> 프로젝트별 History
              </span>
            </div>
          </div>

          <div className="investigation-card card">
            <div className="investigation-topbar">
              <span className="window-lights">
                <i />
                <i />
                <i />
              </span>
              <span className="mono">live investigation</span>
              <span className="live-badge">
                <span className="status-dot" /> verified
              </span>
            </div>
            <div className="question-preview">
              <span>Q</span>
              <p>
                완제품 300002의 구성품과 각 공정·품질검사 결과를 보여줘.
              </p>
            </div>
            <div className="path-preview" aria-label="RCA 관계 경로 예시">
              <div className="path-node root-node">
                <small>Cylinder</small>
                <strong>300002</strong>
              </div>
              <span className="path-edge">ASSEMBLED_FROM</span>
              <div className="path-split">
                <div className="path-node">
                  <small>Bottom</small>
                  <strong>103504</strong>
                </div>
                <div className="path-node">
                  <small>Rod</small>
                  <strong>200102</strong>
                </div>
              </div>
              <span className="path-edge">UNDERWENT</span>
              <div className="path-node accent-node">
                <small>Process</small>
                <strong>CNC milling</strong>
              </div>
            </div>
            <div className="cypher-preview mono">
              <span>Cypher · validated</span>
              <code>
                MATCH (c:Cylinder)-[:ASSEMBLED_FROM]-&gt;(p:Part)
                <br />
                OPTIONAL MATCH (p)-[:UNDERWENT]-&gt;(run:ProcessRun)
                <br />
                RETURN c, p, run
              </code>
            </div>
          </div>
        </div>
      </section>

      <section className="trust-strip">
        <div className="shell trust-grid">
          <div>
            <strong>802</strong>
            <span>assembled products</span>
          </div>
          <div>
            <strong>95.6%</strong>
            <span>complete genealogy</span>
          </div>
          <div>
            <strong>61.5%</strong>
            <span>blind semantic accuracy</span>
          </div>
          <div>
            <strong>7</strong>
            <span>relationship types</span>
          </div>
        </div>
      </section>

      <ProjectOverview />

      <section className="shell page-section">
        <span className="eyebrow">What the system proves</span>
        <h2 className="section-title">
          AI 답변보다
          <br />
          검증 경로를 설계합니다.
        </h2>
        <div className="capability-grid">
          {CAPABILITIES.map((item) => (
            <article className="capability-card subtle-card" key={item.number}>
              <div>
                <item.icon size={22} />
                <span>{item.number}</span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="workflow-section">
        <div className="shell workflow-grid">
          <div>
            <span className="eyebrow">Agent workflow</span>
            <h2 className="section-title">실행 전에 의심하고, 실행 후에 증명합니다.</h2>
            <p className="lede">
              생성된 쿼리를 바로 실행하지 않습니다. 쓰기 위험과 스키마
              오류를 검사하고, 실패하면 수정한 뒤 다시 검증합니다.
            </p>
            <Link href="/query" className="secondary-button">
              RCA 질문 흐름 보기 <ArrowRight size={16} />
            </Link>
          </div>
          <div className="pipeline-list">
            {PIPELINE.map(([title, body], index) => (
              <article key={title}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{title}</strong>
                  <p>{body}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="shell page-section">
        <div className="cta-panel card">
          <div>
            <span className="eyebrow">Start with evidence</span>
            <h2>공장 데이터를 묻는 새로운 인터페이스.</h2>
            <p>
              질문, Cypher, 조회 결과, 관계 경로를 한 화면에서 비교해
              보세요.
            </p>
          </div>
          <div className="cta-icons" aria-hidden="true">
            <Search />
            <Sparkles />
            <Database />
          </div>
          <Link href="/query" className="primary-button">
            Query Studio 열기 <ArrowRight size={17} />
          </Link>
        </div>
      </section>
    </>
  );
}
