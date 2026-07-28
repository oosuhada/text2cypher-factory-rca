"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useProject } from "@/components/project-context";
import {
  examplesForProject,
} from "@/components/query/query-config";
import { QueryConversationPanel } from "@/components/query/query-conversation-panel";
import { QueryEvidencePanel } from "@/components/query/query-evidence-panel";
import { QuerySidebar } from "@/components/query/query-sidebar";
import { useQuerySession } from "@/components/query/use-query-session";

export function QueryWorkspace() {
  const {
    projects,
    activeProject,
    readiness,
    loading: projectLoading,
    switching: projectSwitching,
    error: projectError,
    switchProject,
  } = useProject();
  const searchParams = useSearchParams();
  const requestedProjectId = searchParams.get("project_id")?.trim() ?? "";
  const conversationId = searchParams.get("conversation");
  const projectId = activeProject?.project_id ?? "cip-dmd";
  const session = useQuerySession(projectId, conversationId);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const requestedProjectExists =
    !requestedProjectId ||
    projects.some(
      (project) => project.project_id === requestedProjectId,
    );
  const projectContextPending = Boolean(
    requestedProjectId &&
      requestedProjectId !== activeProject?.project_id,
  );
  const queryEnabled = Boolean(
    readiness?.can_query &&
      !projectContextPending &&
      !projectSwitching,
  );
  const [projectSwitchError, setProjectSwitchError] = useState<{
    projectId: string;
    message: string;
  } | null>(null);
  const projectRouteError =
    !projectLoading && requestedProjectId && !requestedProjectExists
      ? `프로젝트 '${requestedProjectId}'을 찾을 수 없습니다.`
      : projectContextPending &&
          projectSwitchError?.projectId === requestedProjectId
        ? projectSwitchError.message
        : "";

  useEffect(() => {
    if (
      projectLoading ||
      !requestedProjectId ||
      requestedProjectId === activeProject?.project_id ||
      !requestedProjectExists
    ) {
      return;
    }
    let cancelled = false;
    void switchProject(requestedProjectId).catch((reason) => {
      if (cancelled) return;
      setProjectSwitchError({
        projectId: requestedProjectId,
        message:
          reason instanceof Error
            ? reason.message
            : "요청한 프로젝트로 전환하지 못했습니다.",
      });
    });
    return () => {
      cancelled = true;
    };
  }, [
    activeProject?.project_id,
    projectLoading,
    requestedProjectExists,
    requestedProjectId,
    switchProject,
  ]);

  return (
    <div className="workspace-shell">
      <QuerySidebar
        examples={examplesForProject(projectId)}
        history={session.history}
        queryEnabled={queryEnabled}
        inputRef={inputRef}
        onPreviewQuestion={session.setQuestion}
        onOpenConversation={session.loadConversation}
      />
      <QueryConversationPanel
        activeProject={activeProject}
        readiness={readiness}
        projectLoading={projectLoading}
        projectSwitching={projectSwitching}
        projectContextPending={projectContextPending}
        projectError={projectError}
        projectRouteError={projectRouteError}
        queryEnabled={queryEnabled}
        isEquipmentHistory={projectId === "equipment-history"}
        inputRef={inputRef}
        session={session}
      />
      <QueryEvidencePanel session={session} />
    </div>
  );
}
