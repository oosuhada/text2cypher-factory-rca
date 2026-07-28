"use client";

import { ArrowRight, FolderKanban } from "lucide-react";

import { projectStatusLabel } from "@/lib/product-surface";
import type { Project } from "@/lib/types";

type ProjectCardProps = {
  project: Project;
  active: boolean;
  busy: boolean;
  compact?: boolean;
  updatedLabel?: string;
  onOpenRecommended: () => void;
  onOpenQuery: () => void;
};

export function ProjectCard({
  project,
  active,
  busy,
  compact = false,
  updatedLabel,
  onOpenRecommended,
  onOpenQuery,
}: ProjectCardProps) {
  return (
    <article
      className={`${
        compact ? "project-summary-card" : "project-registry-card"
      } subtle-card ${active ? "active" : ""}`}
    >
      <div className={compact ? "project-summary-top" : undefined}>
        <FolderKanban size={compact ? 18 : 19} />
        <span className="project-status">
          {projectStatusLabel(project.status)}
        </span>
      </div>
      <h3>{project.name}</h3>
      <p>
        {project.domain_type}
        {compact ? ` · ${project.dataset_name}` : ""}
      </p>
      {compact ? (
        <small>
          {project.project_id}
          {updatedLabel ? ` · ${updatedLabel}` : ""}
        </small>
      ) : (
        <dl>
          <div>
            <dt>Dataset</dt>
            <dd>{project.dataset_name}</dd>
          </div>
          <div>
            <dt>Schema</dt>
            <dd>{project.schema_version ?? "미정"}</dd>
          </div>
        </dl>
      )}
      <div className="project-card-actions">
        <button
          type="button"
          className={active ? "ghost-button" : "secondary-button"}
          disabled={busy}
          onClick={onOpenRecommended}
        >
          {busy ? "여는 중…" : "작업 열기"}
        </button>
        <button
          type="button"
          className="ghost-button"
          disabled={busy}
          onClick={onOpenQuery}
        >
          {busy ? "여는 중…" : compact ? "Query 열기" : "Query"}{" "}
          {!compact && <ArrowRight size={14} />}
        </button>
      </div>
    </article>
  );
}
