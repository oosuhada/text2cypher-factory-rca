"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { getProjectReadiness, getProjects } from "@/lib/api";
import type { Project, ProjectReadiness } from "@/lib/types";

type ProjectContextValue = {
  projects: Project[];
  activeProject: Project | null;
  readiness: ProjectReadiness | null;
  loading: boolean;
  switching: boolean;
  error: string;
  refresh: () => Promise<void>;
  refreshReadiness: () => Promise<void>;
  switchProject: (projectId: string) => Promise<void>;
};

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [readiness, setReadiness] =
    useState<ProjectReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const rows = await getProjects();
    setProjects(rows);
    setSelectedProjectId((current) => {
      if (current && rows.some((row) => row.project_id === current)) {
        return current;
      }
      const stored = window.localStorage.getItem(
        "factory-graph-active-project",
      );
      if (stored && rows.some((row) => row.project_id === stored)) {
        return stored;
      }
      return (
        rows.find((row) => row.is_active)?.project_id ??
        rows[0]?.project_id ??
        ""
      );
    });
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      refresh().catch(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  const switchProject = useCallback(
    async (projectId: string) => {
      setSwitching(true);
      setError("");
      setReadiness(null);
      try {
        const nextReadiness = await getProjectReadiness(projectId);
        localStorage.setItem(
          "factory-graph-active-project",
          projectId,
        );
        setSelectedProjectId(projectId);
        setReadiness(nextReadiness);
      } catch (reason) {
        setError(
          reason instanceof Error
            ? reason.message
            : "프로젝트 전환에 실패했습니다.",
        );
        throw reason;
      } finally {
        setSwitching(false);
      }
    },
    [],
  );

  const activeProject =
    projects.find(
      (project) => project.project_id === selectedProjectId,
    ) ?? projects[0] ?? null;
  const refreshReadiness = useCallback(async () => {
    if (!activeProject) {
      setReadiness(null);
      return;
    }
    try {
      setError("");
      setReadiness(
        await getProjectReadiness(activeProject.project_id),
      );
    } catch (reason) {
      setReadiness(null);
      setError(
        reason instanceof Error
          ? reason.message
          : "프로젝트 준비 상태를 확인하지 못했습니다.",
      );
    }
  }, [activeProject]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshReadiness();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshReadiness]);

  const value = useMemo(
    () => ({
      projects,
      activeProject,
      readiness,
      loading,
      switching,
      error,
      refresh,
      refreshReadiness,
      switchProject,
    }),
    [
      projects,
      activeProject,
      readiness,
      loading,
      switching,
      error,
      refresh,
      refreshReadiness,
      switchProject,
    ],
  );
  return (
    <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
  );
}

export function useProject() {
  const value = useContext(ProjectContext);
  if (!value) throw new Error("ProjectProvider가 필요합니다.");
  return value;
}
