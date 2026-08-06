import Link from "next/link";

import { INTERNAL_CONSOLE_URL } from "@/lib/product-surface";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell footer-inner">
        <div>
          <strong>FactoryGraph RCA</strong>
          <p>관계 경로를 숨기지 않는 제조 지식그래프 질의 시스템.</p>
        </div>
        <div className="footer-links">
          <Link href="/projects">Projects</Link>
          <Link href="/query">Query Studio</Link>
          <Link href="/graph">Evidence / Graph</Link>
          <a href={INTERNAL_CONSOLE_URL}>Internal Console</a>
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
