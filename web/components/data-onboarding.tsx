"use client";

import { FormEvent, useState } from "react";
import { CheckCircle2, LoaderCircle, Upload } from "lucide-react";

import { useProject } from "@/components/project-context";
import { createProject, profileDataset } from "@/lib/api";
import type { DatasetProfile } from "@/lib/types";

async function encode(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return { filename: file.name, content_base64: btoa(binary) };
}

export function DataOnboarding() {
  const {
    activeProject,
    readiness,
    refresh,
    refreshReadiness,
    switchProject,
  } = useProject();
  const [files, setFiles] = useState<File[]>([]);
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [createdId, setCreatedId] = useState("");

  const upload = async () => {
    if (!activeProject || !files.length) return;
    setBusy(true);
    setError("");
    try {
      const encoded = await Promise.all(files.map(encode));
      setProfile(await profileDataset(activeProject.project_id, encoded));
      await refreshReadiness();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "업로드 실패");
    } finally {
      setBusy(false);
    }
  };

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const project = await createProject({
        project_id: String(values.get("project_id")),
        name: String(values.get("name")),
        domain_type: String(values.get("domain_type")),
        dataset_name: String(values.get("dataset_name")),
      });
      setCreatedId(project.project_id);
      await refresh();
      await switchProject(project.project_id);
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "프로젝트 생성 실패");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="onboarding-grid">
      <section className="pipeline-progress card">
        {[
          ["Upload", readiness?.upload_count ? "done" : "active"],
          [
            "Mapping",
            readiness?.mapping_approved
              ? "done"
              : readiness?.upload_count
                ? "active"
                : "waiting",
          ],
          [
            "Load",
            readiness?.can_query
              ? "done"
              : readiness?.mapping_approved
                ? "active"
                : "waiting",
          ],
          ["Query", readiness?.can_query ? "active" : "waiting"],
        ].map(([label, state], index) => (
          <div className={`pipeline-progress-step ${state}`} key={label}>
            <span>{index + 1}</span>
            <strong>{label}</strong>
          </div>
        ))}
      </section>
      <section className="card onboarding-panel">
        <h2>1 · 프로젝트 워크스페이스</h2>
        <p>도메인과 데이터셋을 분리해 스키마·대화·그래프를 격리합니다.</p>
        <form className="stack-form" onSubmit={create}>
          <input name="project_id" placeholder="project-id" required />
          <input name="name" placeholder="프로젝트 이름" required />
          <input name="domain_type" placeholder="도메인" required />
          <input name="dataset_name" placeholder="데이터셋 이름" required />
          <button className="secondary-button" disabled={busy}>
            프로젝트 생성
          </button>
        </form>
        {createdId && (
          <span className="inline-success">
            <CheckCircle2 size={15} /> {createdId} 생성·활성화
          </span>
        )}
      </section>
      <section className="card onboarding-panel">
        <h2>2 · 데이터 업로드와 프로파일</h2>
        <p>
          현재 프로젝트: <strong>{activeProject?.name ?? "연결 중"}</strong>
        </p>
        <label className="drop-zone">
          <Upload size={22} />
          <span>CSV/JSON 파일 선택 · 파일당 10MB</span>
          <input
            type="file"
            accept=".csv,.json"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
        </label>
        {files.length > 0 && (
          <p className="selected-files">
            선택됨: {files.map((file) => file.name).join(", ")}
          </p>
        )}
        <button
          className="primary-button"
          disabled={busy || !files.length || !activeProject}
          onClick={() => void upload()}
        >
          {busy ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />}
          업로드 및 프로파일링
        </button>
      </section>
      {error && <div className="inline-error">{error}</div>}
      {profile && (
        <section className="card profile-panel">
          <h2>프로파일 결과 · {profile.upload_id.slice(0, 8)}</h2>
          {profile.files.map((file) => (
            <article key={file.filename}>
              <strong>{file.filename}</strong>
              <span>{file.row_count} rows · {file.column_count} columns</span>
              <div className="profile-table">
                {file.columns.map((column) => (
                  <div key={column.name}>
                    <code>{column.name}</code>
                    <span>{column.inferred_type}</span>
                    <span>missing {Math.round(column.missing_rate * 100)}%</span>
                    <span>{column.identity_candidate ? "ID candidate" : ""}</span>
                  </div>
                ))}
              </div>
            </article>
          ))}
          <a className="primary-button" href="/schema">
            Schema Studio에서 매핑 검토
          </a>
        </section>
      )}
    </div>
  );
}
