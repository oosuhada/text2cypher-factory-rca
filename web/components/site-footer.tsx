import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell footer-inner">
        <div>
          <strong>FactoryGraph RCA</strong>
          <p>관계 경로를 숨기지 않는 제조 지식그래프 질의 시스템.</p>
        </div>
        <div className="footer-links">
          <Link href="/query">Query Studio</Link>
          <Link href="/operations">Operations</Link>
          <a
            href="https://github.com/oosuhada/text2cypher-factory-rca"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
