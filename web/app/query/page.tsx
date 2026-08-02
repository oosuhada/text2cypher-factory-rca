import type { Metadata } from "next";
import { Suspense } from "react";

import { QueryWorkspace } from "@/components/query-workspace";

import "./query.css";

export const metadata: Metadata = {
  title: "Query Studio",
};

export default function QueryPage() {
  return (
    <Suspense fallback={<div className="workspace-loading">Loading…</div>}>
      <QueryWorkspace />
    </Suspense>
  );
}
