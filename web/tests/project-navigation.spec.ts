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
  {
    project_id: "cip-dmd",
    name: "CiP-DMD Manufacturing",
    domain_type: "manufacturing-process",
    dataset_name: "cip-dmd",
    schema_version: "1.1.0",
    status: "ready",
    description: "",
    industry: "manufacturing",
    owner: "",
    security_classification: "internal",
    source_type: "file",
    source_version: "cip-dmd-source",
    connector_id: null,
    prompt_version: "cip-dmd-prompt",
    gold_version: "cip-dmd-gold",
    evaluation_version: "cip-dmd-eval",
    created_at: "2026-07-28T01:00:00Z",
    updated_at: "2026-07-28T00:30:00Z",
    is_active: false,
  },
];

function readiness(projectId: string) {
  const ready = projectId === "project-a" || projectId === "cip-dmd";
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

function queryResponse(question: string, projectId: string) {
  const status = question.includes("삭제")
    ? "blocked"
    : question.includes("399999")
      ? "empty"
      : question.includes("문제 있는")
        ? "needs_clarification"
        : question.includes("최근 등록")
          ? "unsupported"
          : "success";
  const answers = {
    success: "자동화된 질의 결과입니다.",
    empty: "조건에 일치하는 결과가 없습니다.",
    blocked: "읽기 전용 정책에 따라 변경 요청을 차단했습니다.",
    needs_clarification: "대상 식별자와 확인 조건을 추가해 주세요.",
    unsupported: "현재 지원하는 제조 RCA 질문 범위를 벗어났습니다.",
  } as const;
  return {
    project_id: projectId,
    question,
    answer: answers[status],
    status,
    cypher: status === "blocked" ? "" : "MATCH (n) RETURN n LIMIT 1",
    rows: status === "success" ? [{ status: "normal" }] : [],
    row_count: status === "success" ? 1 : 0,
    metadata: { project_id: projectId },
    evidence: {
      nodes: [],
      relationships: [],
      node_count: 0,
      relationship_count: 0,
    },
    validation: {
      attempts: 1,
      errors: [],
      trace: [],
      elapsed_ms: 12,
    },
    usage: {},
    caveat: null,
    provider: "gold",
    fallback_reason: null,
  };
}

async function mockProjectApi(
  page: Page,
  options: { failReadinessFor?: string; failQuery?: boolean } = {},
) {
  const queryRequests: string[] = [];
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
    if (
      url.pathname === "/api/v1/query" &&
      request.method() === "POST"
    ) {
      const payload = request.postDataJSON() as {
        question: string;
        project_id: string;
      };
      queryRequests.push(payload.question);
      if (options.failQuery) {
        await route.fulfill({
          status: 503,
          headers,
          json: { detail: "질의 서비스를 사용할 수 없습니다." },
        });
        return;
      }
      await route.fulfill({
        status: 200,
        headers,
        json: queryResponse(payload.question, payload.project_id),
      });
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
  return { queryRequests };
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
  await expect(page.getByLabel("활성 프로젝트", { exact: true })).toHaveValue("project-b");
  await expect(page.getByLabel("제조 관계 질문")).toBeDisabled();

  await page.reload();
  await expect(page).toHaveURL("/query?project_id=project-b");
  await expect(page.getByLabel("활성 프로젝트", { exact: true })).toHaveValue("project-b");
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
  await expect(page).toHaveURL(
    "http://localhost:8501/?workspace=data_sources&project_id=project-b",
  );

  await page.goto("/projects");
  const mappingCard = page
    .getByRole("article")
    .filter({ hasText: "Mapping Project C" });
  await mappingCard.getByRole("button", { name: "작업 열기" }).click();
  await expect(page).toHaveURL(
    "http://localhost:8501/?workspace=pipeline&project_id=project-c",
  );

  await page.goto("/projects");
  const evaluationCard = page
    .getByRole("article")
    .filter({ hasText: "Evaluation Project D" });
  await evaluationCard.getByRole("button", { name: "작업 열기" }).click();
  await expect(page).toHaveURL(
    "http://localhost:8501/?workspace=dashboard&project_id=project-d",
  );

  await page.goto("/projects");
  const readyCard = page
    .getByRole("article")
    .filter({ hasText: "Ready Project A" });
  await readyCard.getByRole("button", { name: "작업 열기" }).click();
  await expect(page).toHaveURL("/query?project_id=project-a");
  await expect(page.getByLabel("활성 프로젝트", { exact: true })).toHaveValue("project-a");
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
  await expect(page.getByLabel("활성 프로젝트", { exact: true })).toHaveValue("project-a");
});

test("demo question previews before one guarded submission", async ({
  page,
}) => {
  const api = await mockProjectApi(page);
  await page.goto("/query?project_id=cip-dmd");

  const composer = page.getByLabel("제조 관계 질문");
  await page
    .getByRole("button", { name: /제품 Genealogy/ })
    .click();
  await expect(composer).toHaveValue(
    "완제품 300002의 구성품, 각 구성품의 공정과 품질검사 결과를 보여줘.",
  );
  expect(api.queryRequests).toHaveLength(0);

  const submit = page.getByRole("button", { name: "질문 전송" });
  await submit.evaluate((button: HTMLButtonElement) => {
    button.click();
    button.click();
  });

  await expect(page.getByText("자동화된 질의 결과입니다.")).toBeVisible();
  await expect(composer).toHaveValue("");
  await expect.poll(() => api.queryRequests.length).toBe(1);
});

test("query result connects answer, evidence and expert review safely", async ({
  page,
}) => {
  await mockProjectApi(page);
  await page.goto("/query?project_id=cip-dmd");

  await page.getByLabel("제조 관계 질문").fill(
    "완제품 300002의 구성품을 보여줘.",
  );
  await page.getByRole("button", { name: "질문 전송" }).click();

  await expect(page.getByText("자동화된 질의 결과입니다.")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "결과와 관계 근거 확인" }),
  ).toHaveAttribute("href", "#query-evidence");
  await expect(
    page.getByRole("tab", { name: "결과", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  const expertReview = page.locator("details.expert-review");
  await expect(expertReview).not.toHaveAttribute("open", "");
  await expect(
    expertReview.getByText("전문가 전용", { exact: false }),
  ).toBeVisible();
});

test("RCA status states guide the user to a safe next action", async ({
  page,
}) => {
  await mockProjectApi(page);
  await page.goto("/query?project_id=cip-dmd");
  const composer = page.getByLabel("제조 관계 질문");

  await composer.fill("완제품 399999의 구성품과 품질검사 결과를 보여줘.");
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(page.getByText("일치하는 관계를 찾지 못했습니다.")).toBeVisible();
  await page.getByRole("button", { name: "조건 바꿔 다시 질문" }).click();
  await expect(composer).toHaveValue(/399999/);

  await composer.fill("압력검사에 실패한 완제품 데이터를 전부 삭제해줘.");
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(page.getByText("조회 전용 서비스에서 변경 요청을 차단했습니다.")).toBeVisible();
  await expect(page.locator("details.expert-review")).toHaveCount(0);

  await page.getByRole("button", { name: "안전한 조회 질문 작성" }).click();
  await composer.fill("문제 있는 부품 찾아줘.");
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(page.getByText("질문 조건을 조금 더 구체화해야 합니다.")).toBeVisible();

  await page.getByRole("button", { name: "조건 추가하기" }).click();
  await composer.fill("최근 등록된 부품 세 개를 보여줘.");
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(page.getByText("현재 그래프가 지원하는 RCA 범위를 벗어났습니다.")).toBeVisible();
});

test("successful RCA result survives History reopen with project context", async ({
  page,
}) => {
  await mockProjectApi(page);
  await page.goto("/query?project_id=cip-dmd");
  await page.getByLabel("제조 관계 질문").fill(
    "완제품 300002의 구성품과 공정 이력을 보여줘.",
  );
  await page.getByRole("button", { name: "질문 전송" }).click();

  await page.getByRole("link", { name: "저장된 기록 보기" }).click();
  await expect(page).toHaveURL("/history?project_id=cip-dmd");
  await expect(page.getByText("조회 완료", { exact: true })).toBeVisible();
  await expect(page.getByText("결과 1건", { exact: true })).toBeVisible();
  await expect(page.getByText("검증 1회", { exact: true })).toBeVisible();
  await expect(page.getByText("gold", { exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: "다시 열기" }).click();
  await expect(page).toHaveURL(/\/query\?project_id=cip-dmd&conversation=/);
  await expect(page.getByText("자동화된 질의 결과입니다.")).toBeVisible();
  await expect(page.getByLabel("활성 프로젝트", { exact: true })).toHaveValue("cip-dmd");
});

test("query service failure offers a retry without losing the question", async ({
  page,
}) => {
  await mockProjectApi(page, { failQuery: true });
  await page.goto("/query?project_id=cip-dmd");
  await page.getByLabel("제조 관계 질문").fill("완제품 300002의 구성품을 보여줘.");
  await page.getByRole("button", { name: "질문 전송" }).click();

  await expect(page.getByText("API 연결 또는 질의 처리 실패")).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 시도" })).toBeVisible();
  await expect(page.getByText("완제품 300002의 구성품을 보여줘.")).toBeVisible();
});

test("mobile header uses a drawer without horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockProjectApi(page);
  await page.goto("/");

  await expect(page.locator(".desktop-project-control")).toBeHidden();
  await expect(page.getByRole("navigation", { name: "주요 작업공간" }))
    .toBeHidden();
  await page.getByRole("button", { name: "메뉴 열기" }).click();

  const navigation = page.getByRole("navigation", {
    name: "주요 작업공간",
  });
  await expect(navigation).toBeVisible();
  await expect(page.getByLabel("모바일 활성 프로젝트", { exact: true })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Query" }))
    .toBeVisible();
  await expect(
    navigation.getByRole("link", { name: "Evidence / Graph" }),
  ).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Data" })).toHaveCount(0);
  await expect(navigation.getByRole("link", { name: "Schema" })).toHaveCount(0);
  await expect(
    navigation.getByRole("link", { name: "Operations" }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("standard laptop header collapses before horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockProjectApi(page);
  await page.goto("/query?project_id=cip-dmd");

  await expect(page.getByRole("button", { name: "메뉴 열기" }))
    .toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
