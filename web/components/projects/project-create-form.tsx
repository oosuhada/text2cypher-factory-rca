"use client";

import { ArrowRight, Plus } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { createProject } from "@/lib/api";

const EMPTY_FORM = {
  project_id: "",
  name: "",
  domain_type: "",
  dataset_name: "",
};

type ProjectCreateFormProps = {
  onCreated: (projectId: string) => Promise<void>;
};

export function ProjectCreateForm({ onCreated }: ProjectCreateFormProps) {
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
      await onCreated(created.project_id);
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
      <button className="primary-button" type="submit" disabled={creating}>
        <Plus size={16} />
        {creating ? "프로젝트 생성 중…" : "프로젝트 생성"}
      </button>
      {createdName ? (
        <Link href="/data" className="secondary-button">
          데이터 등록으로 이동 <ArrowRight size={15} />
        </Link>
      ) : null}
    </form>
  );
}
