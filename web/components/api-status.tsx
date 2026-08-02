"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";

export function ApiStatus() {
  const [status, setStatus] = useState<
    "checking" | "ready" | "degraded" | "offline"
  >("checking");

  useEffect(() => {
    let mounted = true;
    getHealth()
      .then((result) => mounted && setStatus(result.status))
      .catch(() => mounted && setStatus("offline"));
    return () => {
      mounted = false;
    };
  }, []);

  const label = {
    checking: "연결 확인",
    ready: "Graph ready",
    degraded: "부분 연결",
    offline: "API offline",
  }[status];

  return (
    <span
      className={`api-status status-${status === "checking" ? "degraded" : status}`}
      title="FastAPI와 Neo4j 연결 상태"
    >
      <span className="status-dot" />
      {label}
    </span>
  );
}
