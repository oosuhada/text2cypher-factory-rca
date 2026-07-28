import type { Metadata } from "next";

import { PageHeading } from "@/components/page-heading";
import { ProjectWorkspace } from "@/components/project-workspace";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return (
    <div className="shell product-page">
      <PageHeading
        eyebrow="Workspace registry"
        title="Projects"
        description="최근 프로젝트를 다시 열고, 전체 프로젝트의 준비 상태를 확인하거나 새 도메인 프로젝트를 시작합니다."
      />
      <ProjectWorkspace />
    </div>
  );
}
