"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, FolderKanban, Plus } from "lucide-react";
import Link from "next/link";

import { useProject } from "@/components/project-context";
import { createProject } from "@/lib/api";

const EMPTY_FORM = {
  project_id: "",
  name: "",
  domain_type: "",
  dataset_name: "",
};

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
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState("");
  const [createdName, setCreatedName] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setFormError("");
    setCreatedName("");
    try {
      const created = await createProject(form);
      await refresh();
      await switchProject(created.project_id);
      setCreatedName(created.name);
      setForm(EMPTY_FORM);
    } catch (reason) {
      setFormError(
        reason instanceof Error
          ? reason.message
          : "프로젝트 생성에 실패했습니다.",
      );
    } finally {
      setCreating(false);
    }
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
          {projects.map((project) => {
            const active =
              activeProject?.project_id === project.project_id;
            return (
              <article className="project-registry-card subtle-card" key={project.project_id}>
                <div>
                  <FolderKanban size={19} />
                  <span className="project-status">{project.status}</span>
                </div>
                <h3>{project.name}</h3>
                <p>{project.domain_type}</p>
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
                <div className="project-card-actions">
                  <button
                    type="button"
                    className={active ? "ghost-button" : "secondary-button"}
                    disabled={active || switching}
                    onClick={() => void switchProject(project.project_id)}
                  >
                    {active ? "현재 프로젝트" : "프로젝트 전환"}
                  </button>
                  <Link href="/query" className="ghost-button">
                    Query <ArrowRight size={14} />
                  </Link>
                </div>
              </article>
            );
          })}
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
        <form className="project-create-form" onSubmit={submit}>
          <label>
            프로젝트 ID
            <input
              required
              minLength={3}
              pattern="[a-z][a-z0-9-]{2,62}"
              placeholder="semiconductor-yield"
              value={form.project_id}
              onChange={(event) =>
                setForm({ ...form, project_id: event.target.value })
              }
            />
          </label>
          <label>
            프로젝트 이름
            <input
              required
              placeholder="반도체 수율 RCA"
              value={form.name}
              onChange={(event) =>
                setForm({ ...form, name: event.target.value })
              }
            />
          </label>
          <label>
            도메인
            <input
              required
              placeholder="semiconductor-process"
              value={form.domain_type}
              onChange={(event) =>
                setForm({ ...form, domain_type: event.target.value })
              }
            />
          </label>
          <label>
            데이터셋/연결 이름
            <input
              required
              placeholder="Fab process history"
              value={form.dataset_name}
              onChange={(event) =>
                setForm({ ...form, dataset_name: event.target.value })
              }
            />
          </label>
          {formError ? <p className="inline-error">{formError}</p> : null}
          {createdName ? (
            <p className="inline-success">
              {createdName} 프로젝트를 만들고 활성화했습니다.
            </p>
          ) : null}
          <button
            className="primary-button"
            type="submit"
            disabled={creating}
          >
            <Plus size={16} />
            {creating ? "프로젝트 생성 중…" : "프로젝트 생성"}
          </button>
          {createdName ? (
            <Link href="/data" className="secondary-button">
              데이터 등록으로 이동 <ArrowRight size={15} />
            </Link>
          ) : null}
        </form>
      </section>
    </div>
  );
}
