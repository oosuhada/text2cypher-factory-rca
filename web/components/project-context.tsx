"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { activateProject, getProjects } from "@/lib/api";
import type { Project } from "@/lib/types";

type ProjectContextValue = {
  projects: Project[];
  activeProject: Project | null;
  loading: boolean;
  refresh: () => Promise<void>;
  switchProject: (projectId: string) => Promise<void>;
};

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const rows = await getProjects();
    setProjects(rows);
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
      await activateProject(projectId);
      localStorage.setItem("factory-graph-active-project", projectId);
      await refresh();
    },
    [refresh],
  );

  const activeProject =
    projects.find((project) => project.is_active) ?? projects[0] ?? null;
  const value = useMemo(
    () => ({ projects, activeProject, loading, refresh, switchProject }),
    [projects, activeProject, loading, refresh, switchProject],
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
