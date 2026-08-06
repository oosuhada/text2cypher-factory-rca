"use client";

import {
  History,
  Menu,
  MessageSquareText,
  Network,
  DatabaseZap,
  FolderKanban,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ApiStatus } from "@/components/api-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { useProject } from "@/components/project-context";
import {
  PRODUCT_NAVIGATION,
  projectStatusLabel,
  readinessStatusLabel,
} from "@/lib/product-surface";

const NAVIGATION_ICONS = {
  projects: FolderKanban,
  query: MessageSquareText,
  graph: Network,
  history: History,
};

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const {
    projects,
    activeProject,
    readiness,
    switching,
    switchProject,
  } = useProject();
  const statusLabel = readinessStatusLabel(readiness ?? undefined);
  const projectSelector = (className: string) => (
    <div className={`project-control ${className}`}>
      <DatabaseZap size={15} />
      <label>
        <span>Project · {statusLabel}</span>
        <select
          className="project-switcher"
          aria-label={
            className.includes("mobile")
              ? "모바일 활성 프로젝트"
              : "활성 프로젝트"
          }
          value={activeProject?.project_id ?? ""}
          disabled={!activeProject || switching}
          onChange={(event) =>
            void switchProject(event.target.value).catch(() => undefined)
          }
        >
          {projects.map((project) => (
            <option key={project.project_id} value={project.project_id}>
              {project.name} · {projectStatusLabel(project.status)}
            </option>
          ))}
        </select>
      </label>
    </div>
  );

  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link href="/" className="brand-lockup" aria-label="FactoryGraph 홈">
          <span className="brand-mark">
            <span />
            <span />
            <span />
          </span>
          <span>FactoryGraph</span>
          <small>RCA</small>
        </Link>

        {open ? (
          <button
            type="button"
            className="nav-backdrop"
            aria-label="모바일 메뉴 닫기"
            onClick={() => setOpen(false)}
          />
        ) : null}

        <nav
          className={`primary-nav ${open ? "nav-open" : ""}`}
          id="primary-navigation"
          aria-label="주요 작업공간"
        >
          {projectSelector("mobile-project-control")}
          {PRODUCT_NAVIGATION.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = NAVIGATION_ICONS[item.icon];
            return (
              <Link
                href={item.href}
                key={item.href}
                className={active ? "nav-link active" : "nav-link"}
                onClick={() => setOpen(false)}
              >
                <Icon size={15} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="header-actions">
          {projectSelector("desktop-project-control")}
          <ApiStatus />
          <ThemeToggle />
          <button
            type="button"
            className="icon-button menu-button"
            aria-label={open ? "메뉴 닫기" : "메뉴 열기"}
            aria-expanded={open}
            aria-controls="primary-navigation"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
      </div>
    </header>
  );
}
