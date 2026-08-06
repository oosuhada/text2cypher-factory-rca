import { expect, type Page, test } from "@playwright/test";

const API_ORIGIN = "http://127.0.0.1:8000";
const APP_ORIGIN = "http://127.0.0.1:3100";

const projects = [
  {
    project_id: "project-a",
    name: "Ready Project A",
    domain_type: "manufacturing-process",
    dataset_name: "ready-fixture",
    schema_version: "1.0.0",
    status: "ready",
    description: "",
    industry: "manufacturing",
    owner: "",
    security_classification: "internal",
    source_type: "file",
    source_version: "source-a",
    connector_id: null,
    prompt_version: "prompt-a",
    gold_version: "gold-a",
    evaluation_version: "eval-a",
    created_at: "2026-07-28T00:00:00Z",
    updated_at: "2026-07-28T02:00:00Z",
    is_active: true,
  },
  {
    project_id: "project-b",
    name: "Draft Project B",
    domain_type: "equipment-history",
    dataset_name: "draft-fixture",
    schema_version: null,
    status: "draft",
    description: "",
    industry: "manufacturing",
    owner: "",
    security_classification: "internal",
    source_type: "file",
    source_version: null,
    connector_id: null,
    prompt_version: null,
    gold_version: null,
    evaluation_version: null,
    created_at: "2026-07-28T01:00:00Z",
    updated_at: "2026-07-28T03:00:00Z",
    is_active: false,
  },
  {
    project_id: "project-c",
    name: "Mapping Project C",
    domain_type: "material-genealogy",
    dataset_name: "mapping-fixture",
    schema_version: null,
    status: "mapping_review",
    description: "",
    industry: "manufacturing",
    owner: "",
    security_classification: "internal",
    source_type: "file",
    source_version: "source-c",
    connector_id: null,
    prompt_version: null,
    gold_version: null,
    evaluation_version: null,
    created_at: "2026-07-28T01:00:00Z",
    updated_at: "2026-07-28T04:00:00Z",
    is_active: false,
  },
  {
    project_id: "project-d",
    name: "Evaluation Project D",
    domain_type: "quality-traceability",
    dataset_name: "evaluation-fixture",
    schema_version: "1.0.0",
    status: "evaluation_required",
    description: "",
    industry: "manufacturing",
    owner: "",
    security_classification: "internal",
    source_type: "file",
    source_version: "source-d",
    connector_id: null,
    prompt_version: "prompt-d",
    gold_version: "gold-d",
    evaluation_version: null,
    created_at: "2026-07-28T01:00:00Z",
    updated_at: "2026-07-28T05:00:00Z",
    is_active: false,
  },
];

function readiness(projectId: string) {
  const ready = projectId === "project-a";
  const nextAction =
    projectId === "project-b"
      ? "upload"
      : projectId === "project-c"
        ? "map"
        : projectId === "project-d"
          ? "evaluate"
          : "query";
  const lifecycleStatus =
    projects.find((project) => project.project_id === projectId)?.status ??
    "draft";
  return {
    project_id: projectId,
    lifecycle_status: lifecycleStatus,
    source_type: "file",
    upload_count: ready ? 1 : 0,
    mapping_approved: ready,
    schema_available: ready,
    node_count: ready ? 120 : 0,
    relationship_count: ready ? 240 : 0,
    can_query: ready,
    can_load: ready,
    eligible_for_ready: ready,
    next_action: nextAction,
    checks: {},
    versions: {},
    artifacts: {},
    transitions: [],
  };
}

async function mockProjectApi(
  page: Page,
  options: { failReadinessFor?: string } = {},
) {
  await page.addInitScript(() => {
    window.localStorage.clear();
  });
  await page.route(`${API_ORIGIN}/api/v1/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = {
      "access-control-allow-origin": APP_ORIGIN,
      "access-control-allow-methods": "GET,POST,OPTIONS",
      "access-control-allow-headers": "content-type",
      "content-type": "application/json",
    };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    if (url.pathname === "/api/v1/health") {
      await route.fulfill({
        status: 200,
        headers,
        json: { status: "degraded", checks: [] },
      });
      return;
    }
    if (url.pathname === "/api/v1/projects") {
      await route.fulfill({ status: 200, headers, json: projects });
      return;
    }
    const match = url.pathname.match(
      /^\/api\/v1\/projects\/([^/]+)\/readiness$/,
    );
    if (match) {
      const projectId = decodeURIComponent(match[1]);
      if (options.failReadinessFor === projectId) {
        await route.fulfill({
          status: 503,
          headers,
          json: { detail: "프로젝트 준비 상태를 확인하지 못했습니다." },
        });
        return;
      }
      await route.fulfill({
        status: 200,
        headers,
        json: readiness(projectId),
      });
      return;
    }
    await route.fulfill({
      status: 404,
      headers,
      json: { detail: `Unmocked endpoint: ${url.pathname}` },
    });
  });
}

test("card Query atomically switches project and survives refresh", async ({
  page,
}) => {
  await mockProjectApi(page);
  await page.goto("/");

  const draftCard = page
    .getByRole("article")
    .filter({ hasText: "Draft Project B" });
  await draftCard.getByRole("button", { name: "Query 열기" }).click();

  await expect(page).toHaveURL("/query?project_id=project-b");
  await expect(
    page.getByRole("heading", {
      name: "Draft Project B에 질문하세요.",
    }),
  ).toBeVisible();
  await expect(page.getByLabel("활성 프로젝트")).toHaveValue("project-b");
  await expect(page.getByLabel("제조 관계 질문")).toBeDisabled();

  await page.reload();
  await expect(page).toHaveURL("/query?project_id=project-b");
  await expect(page.getByLabel("활성 프로젝트")).toHaveValue("project-b");
  await expect(
    page.getByRole("heading", {
      name: "Draft Project B에 질문하세요.",
    }),
  ).toBeVisible();
});

test("recommended project entry follows readiness", async ({ page }) => {
  await mockProjectApi(page);
  await page.goto("/projects");

  const draftCard = page
    .getByRole("article")
    .filter({ hasText: "Draft Project B" });
  await draftCard.getByRole("button", { name: "작업 열기" }).click();
  await expect(page).toHaveURL("/data?project_id=project-b");
  await expect(page.getByLabel("활성 프로젝트")).toHaveValue("project-b");

  await page.goto("/projects");
  const mappingCard = page
    .getByRole("article")
    .filter({ hasText: "Mapping Project C" });
  await mappingCard.getByRole("button", { name: "작업 열기" }).click();
  await expect(page).toHaveURL("/schema?project_id=project-c");
  await expect(page.getByLabel("활성 프로젝트")).toHaveValue("project-c");

  await page.goto("/projects");
  const evaluationCard = page
    .getByRole("article")
    .filter({ hasText: "Evaluation Project D" });
  await evaluationCard.getByRole("button", { name: "작업 열기" }).click();
  await expect(page).toHaveURL("/operations?project_id=project-d");
  await expect(page.getByLabel("활성 프로젝트")).toHaveValue("project-d");

  await page.goto("/projects");
  const readyCard = page
    .getByRole("article")
    .filter({ hasText: "Ready Project A" });
  await readyCard.getByRole("button", { name: "작업 열기" }).click();
  await expect(page).toHaveURL("/query?project_id=project-a");
  await expect(page.getByLabel("활성 프로젝트")).toHaveValue("project-a");
});

test("failed project switch never navigates", async ({ page }) => {
  await mockProjectApi(page, { failReadinessFor: "project-b" });
  await page.goto("/");

  const draftCard = page
    .getByRole("article")
    .filter({ hasText: "Draft Project B" });
  await draftCard.getByRole("button", { name: "Query 열기" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByText("프로젝트 준비 상태를 확인하지 못했습니다."))
    .toBeVisible();
  await expect(page.getByLabel("활성 프로젝트")).toHaveValue("project-a");
});
