"use client";

import { useProject } from "@/components/project-context";
import { ProjectCard } from "@/components/projects/project-card";
import { ProjectCreateForm } from "@/components/projects/project-create-form";
import { useProjectNavigation } from "@/components/use-project-navigation";

export function ProjectWorkspace() {
  const {
    projects,
    activeProject,
    loading,
    switching,
    error,
    refresh,
    switchProject,
  } = useProject();
  const { openProject, openingProjectId } = useProjectNavigation();

  async function finishProjectCreation(projectId: string) {
    await refresh();
    await switchProject(projectId);
  }

  return (
    <div className="project-workspace">
      <section aria-labelledby="all-projects-title">
        <div className="workspace-section-heading">
          <div>
            <span className="eyebrow">Registry</span>
            <h2 id="all-projects-title">모든 프로젝트</h2>
          </div>
          <span>{projects.length} projects</span>
        </div>
        {error ? <p className="inline-error">{error}</p> : null}
        <div className="all-project-grid" aria-busy={loading}>
          {projects.map((project) => (
            <ProjectCard
              key={project.project_id}
              project={project}
              active={activeProject?.project_id === project.project_id}
              busy={
                switching || openingProjectId === project.project_id
              }
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

      <section
        className="new-project-panel card"
        id="new-project"
        aria-labelledby="new-project-title"
      >
        <div>
          <span className="eyebrow">Create workspace</span>
          <h2 id="new-project-title">새 프로젝트 만들기</h2>
          <p>
            프로젝트 기본정보를 등록한 뒤 Data Pipeline에서 파일 업로드나
            Neo4j 연결을 진행합니다.
          </p>
        </div>
        <ProjectCreateForm onCreated={finishProjectCreation} />
      </section>
    </div>
  );
}
