import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { internalConsoleUrl } from "@/lib/product-surface";

export const metadata: Metadata = { title: "Internal Pipeline Console" };

type PageProps = {
  searchParams: Promise<{ project_id?: string | string[] }>;
};

export default async function SchemaPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const projectId = Array.isArray(params.project_id)
    ? params.project_id[0]
    : params.project_id;
  redirect(internalConsoleUrl("pipeline", projectId));
}
