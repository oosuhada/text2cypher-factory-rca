"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, LoaderCircle } from "lucide-react";

import { useProject } from "@/components/project-context";
import {
  approveGraphMapping,
  getDatasetUploads,
  loadProjectGraph,
  previewGraphMapping,
} from "@/lib/api";
import type { DatasetProfile } from "@/lib/types";

function defaultMapping(profile: DatasetProfile) {
  const file = profile.files[0];
  const identity =
    file.columns.find((column) => column.identity_candidate)?.name ??
    file.columns[0]?.name ??
    "id";
  return {
    title: `${profile.project_id} graph`,
    nodes: [{
      label: "Record",
      source_file: file.filename,
      identity,
      properties: Object.fromEntries(
        file.columns.map((column) => [column.name, column.name]),
      ),
    }],
    relationships: [],
  };
}

export function SchemaStudio() {
  const { activeProject, refresh } = useProject();
  const projectId = activeProject?.project_id ?? "";
  const [uploads, setUploads] = useState<DatasetProfile[]>([]);
  const [uploadId, setUploadId] = useState("");
  const [mappingText, setMappingText] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selected = useMemo(
    () => uploads.find((upload) => upload.upload_id === uploadId),
    [uploads, uploadId],
  );

  useEffect(() => {
    if (!projectId) return;
    getDatasetUploads(projectId)
      .then((response) => {
        setUploads(response.uploads);
        const first = response.uploads[0];
        setUploadId(first?.upload_id ?? "");
        setMappingText(
          first ? JSON.stringify(defaultMapping(first), null, 2) : "",
        );
      })
      .catch((reason) =>
        setError(reason instanceof Error ? reason.message : "업로드 조회 실패"),
      );
  }, [projectId]);

  const run = async (approve: boolean) => {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const mapping = JSON.parse(mappingText) as Record<string, unknown>;
      const response = approve
        ? await approveGraphMapping(projectId, uploadId, mapping)
        : await previewGraphMapping(projectId, uploadId, mapping);
      setResult(response);
      if (approve) await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "매핑 검증 실패");
    } finally {
      setBusy(false);
    }
  };

  const load = async () => {
    setBusy(true);
    setError("");
    try {
      setResult(await loadProjectGraph(projectId, uploadId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "그래프 적재 실패");
    } finally {
      setBusy(false);
    }
  };

  if (!uploads.length) {
    return (
      <div className="empty-state card">
        <h2>프로파일된 데이터가 없습니다.</h2>
        <p>Data Pipeline에서 CSV/JSON을 먼저 업로드하세요.</p>
        <a href="/data" className="primary-button">데이터 업로드</a>
      </div>
    );
  }
  return (
    <div className="schema-studio-grid">
      <section className="card onboarding-panel">
        <label>
          Upload profile
          <select
            value={uploadId}
            onChange={(event) => {
              const next = uploads.find(
                (upload) => upload.upload_id === event.target.value,
              );
              setUploadId(event.target.value);
              if (next) setMappingText(JSON.stringify(defaultMapping(next), null, 2));
            }}
          >
            {uploads.map((upload) => (
              <option key={upload.upload_id} value={upload.upload_id}>
                {upload.upload_id.slice(0, 8)} · {upload.files.length} files
              </option>
            ))}
          </select>
        </label>
        <textarea
          className="mapping-editor"
          value={mappingText}
          onChange={(event) => setMappingText(event.target.value)}
          spellCheck={false}
        />
        <div className="button-row">
          <button className="secondary-button" disabled={busy} onClick={() => void run(false)}>
            매핑 미리보기
          </button>
          <button className="primary-button" disabled={busy} onClick={() => void run(true)}>
            {busy && <LoaderCircle className="spin" size={15} />} 검토 후 승인
          </button>
        </div>
      </section>
      <section className="card onboarding-panel">
        <h2>Schema contract / load evidence</h2>
        {result ? <pre className="json-preview">{JSON.stringify(result, null, 2)}</pre> : (
          <p>미리보기를 실행하면 생성될 노드·관계와 예상 행 수가 표시됩니다.</p>
        )}
        <label>
          적재 확인 문구
          <input
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder={projectId}
          />
        </label>
        <button
          className="primary-button"
          disabled={busy || confirmation !== projectId}
          onClick={() => void load()}
        >
          <CheckCircle2 size={15} /> 승인된 그래프 적재
        </button>
        {error && <div className="inline-error">{error}</div>}
      </section>
    </div>
  );
}
