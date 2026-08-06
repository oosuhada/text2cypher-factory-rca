"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { useProject } from "@/components/project-context";
import type { ProjectReadiness } from "@/lib/types";

type ProjectOpenIntent = "recommended" | "query";

const NEXT_ACTION_ROUTE: Record<ProjectReadiness["next_action"], string> = {
  upload: "/data",
  connect: "/data",
  map: "/schema",
  load: "/schema",
  validate: "/schema",
  evaluate: "/operations",
  activate: "/operations",
  query: "/query",
};

export function projectRoute(
  projectId: string,
  readiness: ProjectReadiness,
  intent: ProjectOpenIntent = "recommended",
) {
  const path =
    intent === "query" || readiness.can_query
      ? "/query"
      : NEXT_ACTION_ROUTE[readiness.next_action];
  const params = new URLSearchParams({ project_id: projectId });
  return `${path}?${params.toString()}`;
}

export function useProjectNavigation() {
  const router = useRouter();
  const { switchProject } = useProject();
  const [openingProjectId, setOpeningProjectId] = useState("");

  const openProject = useCallback(
    async (
      projectId: string,
      intent: ProjectOpenIntent = "recommended",
    ) => {
      setOpeningProjectId(projectId);
      try {
        const readiness = await switchProject(projectId);
        router.push(projectRoute(projectId, readiness, intent));
      } catch {
        // ProjectContext exposes the actionable error. Never navigate when
        // readiness validation or project switching fails.
      } finally {
        setOpeningProjectId("");
      }
    },
    [router, switchProject],
  );

  return { openProject, openingProjectId };
}
