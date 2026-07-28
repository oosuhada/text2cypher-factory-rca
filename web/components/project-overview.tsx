"use client";

import { ArrowRight, Plus } from "lucide-react";
import Link from "next/link";

import { useProject } from "@/components/project-context";
import { ProjectCard } from "@/components/projects/project-card";
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
        {loading && (
          <article className="project-summary-card subtle-card">
            <span className="project-status">불러오는 중</span>
            <h3>프로젝트 목록을 확인하고 있습니다.</h3>
          </article>
        )}
        {!loading && recentProjects.length === 0 && (
          <article className="project-summary-card subtle-card">
            <span className="project-status">Empty</span>
            <h3>아직 등록된 프로젝트가 없습니다.</h3>
            <Link href="/projects#new-project" className="secondary-button">
              첫 프로젝트 만들기
            </Link>
          </article>
        )}
        {recentProjects.map((project) => (
          <ProjectCard
            compact
            key={project.project_id}
            project={project}
            active={activeProject?.project_id === project.project_id}
            busy={switching || openingProjectId === project.project_id}
            updatedLabel={relativeProjectTime(project.updated_at)}
            onOpenRecommended={() =>
              void openProject(project.project_id, "recommended")
            }
            onOpenQuery={() =>
              void openProject(project.project_id, "query")
            }
          />
        ))}
      </div>
    </section>
  );
}
