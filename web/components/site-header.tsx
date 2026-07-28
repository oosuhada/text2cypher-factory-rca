"use client";

import {
  Activity,
  Database,
  History,
  Menu,
  MessageSquareText,
  Network,
  DatabaseZap,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ApiStatus } from "@/components/api-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { useProject } from "@/components/project-context";

const NAVIGATION = [
  { href: "/query", label: "Query", icon: MessageSquareText },
  { href: "/graph", label: "Graph", icon: Network },
  { href: "/history", label: "History", icon: History },
  { href: "/data", label: "Data", icon: Database },
  { href: "/schema", label: "Schema", icon: Workflow },
  { href: "/operations", label: "Operations", icon: Activity },
];

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
  const statusLabel = readiness?.can_query
    ? `${readiness.node_count.toLocaleString()} nodes`
    : readiness?.next_action === "evaluate"
      ? "Evaluation required"
      : readiness?.next_action === "connect"
        ? "Connection required"
    : readiness?.next_action === "load"
      ? "Load required"
      : readiness?.next_action === "map"
        ? "Mapping required"
        : "Upload required";

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

        <nav className={`primary-nav ${open ? "nav-open" : ""}`}>
          {NAVIGATION.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                href={item.href}
                key={item.href}
                className={active ? "nav-link active" : "nav-link"}
                onClick={() => setOpen(false)}
              >
                <item.icon size={15} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="header-actions">
          <div className="project-control">
            <DatabaseZap size={15} />
            <label>
              <span>Project · {statusLabel}</span>
              <select
                className="project-switcher"
                aria-label="활성 프로젝트"
                value={activeProject?.project_id ?? ""}
                disabled={!activeProject || switching}
                onChange={(event) =>
                  void switchProject(event.target.value)
                }
              >
                {projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name} · {project.status}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <ApiStatus />
          <ThemeToggle />
          <button
            type="button"
            className="icon-button menu-button"
            aria-label={open ? "메뉴 닫기" : "메뉴 열기"}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
      </div>
    </header>
  );
}
