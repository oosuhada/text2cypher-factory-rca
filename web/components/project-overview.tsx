"use client";

import { ArrowRight, FolderKanban, Plus } from "lucide-react";
import Link from "next/link";

import { useProject } from "@/components/project-context";
import { useProjectNavigation } from "@/components/use-project-navigation";

function relativeProjectTime(value: string) {
  const elapsed = Date.now() - new Date(value).getTime();
  const minutes = Math.max(1, Math.floor(elapsed / 60_000));
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export function ProjectOverview() {
  const {
    projects,
    activeProject,
    loading,
    switching,
    error,
  } = useProject();
  const { openProject, openingProjectId } = useProjectNavigation();
  const recentProjects = [...projects]
    .sort(
      (left, right) =>
        new Date(right.updated_at).getTime() -
        new Date(left.updated_at).getTime(),
    )
    .slice(0, 3);

  return (
    <section className="shell page-section project-overview">
      <div className="section-heading-row">
        <div>
          <span className="eyebrow">Workspace</span>
          <h2 className="section-title">최근 프로젝트</h2>
          <p className="lede">
            마지막으로 작업한 그래프를 열거나 새로운 도메인 프로젝트를
            시작합니다.
          </p>
        </div>
        <div className="project-overview-actions">
          <Link href="/projects" className="secondary-button">
            모든 프로젝트 보기 <ArrowRight size={16} />
          </Link>
          <Link href="/projects#new-project" className="primary-button">
            <Plus size={16} /> 새 프로젝트 만들기
          </Link>
        </div>
      </div>

      {error ? <p className="inline-error">{error}</p> : null}
      <div className="recent-project-grid" aria-busy={loading}>
        {loading ? (
          <article className="project-summary-card subtle-card">
            <span className="project-status">불러오는 중</span>
            <h3>프로젝트 목록을 확인하고 있습니다.</h3>
          </article>
        ) : null}
        {!loading && recentProjects.length === 0 ? (
          <article className="project-summary-card subtle-card">
            <span className="project-status">Empty</span>
            <h3>아직 등록된 프로젝트가 없습니다.</h3>
            <Link href="/projects#new-project" className="secondary-button">
              첫 프로젝트 만들기
            </Link>
          </article>
        ) : null}
        {recentProjects.map((project) => {
          const active =
            activeProject?.project_id === project.project_id;
          return (
            <article
              className={`project-summary-card subtle-card ${
                active ? "active" : ""
              }`}
              key={project.project_id}
            >
              <div className="project-summary-top">
                <FolderKanban size={18} />
                <span className="project-status">{project.status}</span>
              </div>
              <h3>{project.name}</h3>
              <p>
                {project.domain_type} · {project.dataset_name}
              </p>
              <small>
                {project.project_id} ·{" "}
                {relativeProjectTime(project.updated_at)}
              </small>
              <div className="project-card-actions">
                <button
                  type="button"
                  className={active ? "ghost-button" : "secondary-button"}
                  disabled={switching || Boolean(openingProjectId)}
                  onClick={() =>
                    void openProject(project.project_id, "recommended")
                  }
                >
                  {openingProjectId === project.project_id
                    ? "여는 중…"
                    : "작업 열기"}
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={switching || Boolean(openingProjectId)}
                  onClick={() =>
                    void openProject(project.project_id, "query")
                  }
                >
                  {openingProjectId === project.project_id
                    ? "여는 중…"
                    : "Query 열기"}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
