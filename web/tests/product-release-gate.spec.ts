import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, type Page, test } from "@playwright/test";

const API_ORIGIN = "http://127.0.0.1:8000";
const APP_ORIGIN = "http://127.0.0.1:3100";
const baselinePath = resolve(
  process.cwd(),
  "../evaluation/product_user_release_baseline.json",
);
const baseline = JSON.parse(readFileSync(baselinePath, "utf-8")) as {
  required_product_routes: { path: string; heading: string }[];
  viewport_widths: number[];
  deployment_forbidden_copy: string[];
  product_navigation: string[];
  fixtures: {
    long_project_name: string;
    empty_project_id: string;
    large_result_rows: number;
    query_error_status: number;
  };
};

type Project = {
  project_id: string;
  name: string;
  domain_type: string;
  dataset_name: string;
  schema_version: string | null;
  status: "ready" | "draft";
  description: string;
  industry: string;
  owner: string;
  security_classification: string;
  source_type: "file";
  source_version: string | null;
  connector_id: null;
  prompt_version: string | null;
  gold_version: string | null;
  evaluation_version: string | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
};

type MockOptions = {
  projects?: Project[];
  failQuery?: boolean;
  largeRows?: number;
};

const cipProject: Project = {
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
  created_at: "2026-07-28T00:00:00Z",
  updated_at: "2026-07-29T00:00:00Z",
  is_active: true,
};

const longProject: Project = {
  ...cipProject,
  project_id: "long-project",
  name: baseline.fixtures.long_project_name,
  dataset_name: "long-project-fixture",
  is_active: false,
};

function readiness(projectId: string) {
  return {
    project_id: projectId,
    lifecycle_status: "ready",
    source_type: "file",
    upload_count: 1,
    mapping_approved: true,
    schema_available: true,
    node_count: 120,
    relationship_count: 240,
    can_query: true,
    can_load: true,
    eligible_for_ready: true,
    next_action: "query",
    checks: {},
    versions: {},
    artifacts: {},
    transitions: [],
  };
}

function queryResponse(question: string, projectId: string, rowCount: number) {
  const documentQuestion = /매뉴얼|SOP/i.test(question);
  const documentOnly = /매뉴얼에서|SOP에서/i.test(question);
  const status = question.includes("삭제")
    ? "blocked"
    : question.includes("399999")
      ? "empty"
      : "success";
  const rows =
    status === "success" && !documentOnly
      ? Array.from({ length: rowCount }, (_, index) => ({
          part_id: `P-${String(index + 1).padStart(4, "0")}`,
          process: `공정 ${index + 1}`,
          quality_result: index % 2 === 0 ? "PASS" : "REVIEW",
        }))
      : [];
  return {
    project_id: projectId,
    question,
    answer:
      status === "blocked"
        ? "읽기 전용 정책에 따라 변경 요청을 차단했습니다."
        : status === "empty"
          ? "조건에 일치하는 결과가 없습니다."
          : documentOnly
            ? "[quality-inspection-sop@1.0:p1] 압력검사 실패 시 상류 공정과 구성품을 확인합니다."
            : "자동화된 질의 결과입니다.",
    status,
    cypher:
      status === "blocked" || documentOnly
        ? ""
        : "MATCH (n) RETURN n LIMIT 120",
    rows,
    row_count: rows.length,
    metadata: { project_id: projectId, schema_version: "1.1.0" },
    evidence: {
      nodes:
        status === "success" && !documentOnly
          ? [
              {
                id: "Cylinder:300002",
                labels: ["Cylinder"],
                properties: { part_id: "300002" },
              },
              {
                id: "ProcessRun:run-1",
                labels: ["ProcessRun"],
                properties: { run_id: "run-1" },
              },
            ]
          : [],
      relationships:
        status === "success" && !documentOnly
          ? [
              {
                id: "rel-1",
                type: "UNDERWENT",
                source: "Cylinder:300002",
                target: "ProcessRun:run-1",
                properties: {},
              },
            ]
          : [],
      node_count: status === "success" && !documentOnly ? 2 : 0,
      relationship_count: status === "success" && !documentOnly ? 1 : 0,
      documents: documentQuestion
        ? [
            {
              citation_id: "quality-inspection-sop@1.0:p1",
              document_id: "quality-inspection-sop",
              title: "제조 품질검사 SOP",
              version: "1.0",
              document_type: "quality_standard",
              page_number: 1,
              section_title: "압력검사 실패 대응",
              text: "압력검사 실패 시 상류 공정과 구성품을 확인합니다.",
              score: 0.91,
              is_current: true,
              source_filename: "quality-inspection-sop.md",
            },
          ]
        : [],
    },
    validation: {
      attempts: 1,
      errors: [],
      trace: [{ step: "read-only" }],
      elapsed_ms: 12,
      execution_verified: status !== "blocked",
    },
    usage: {},
    caveat: null,
    provider: documentOnly ? "llamaindex" : "gold",
    fallback_reason: null,
  };
}

async function mockProductApi(page: Page, options: MockOptions = {}) {
  const projects = options.projects ?? [cipProject, longProject];
  const queryRequests: string[] = [];
  await page.addInitScript(() => window.localStorage.clear());
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
        json: { status: "ready", checks: [] },
      });
      return;
    }
    if (url.pathname === "/api/v1/projects") {
      await route.fulfill({ status: 200, headers, json: projects });
      return;
    }
    const readinessMatch = url.pathname.match(
      /^\/api\/v1\/projects\/([^/]+)\/readiness$/,
    );
    if (readinessMatch) {
      await route.fulfill({
        status: 200,
        headers,
        json: readiness(decodeURIComponent(readinessMatch[1])),
      });
      return;
    }
    if (url.pathname === "/api/v1/query" && request.method() === "POST") {
      const payload = request.postDataJSON() as {
        question: string;
        project_id: string;
      };
      queryRequests.push(payload.question);
      if (options.failQuery) {
        await route.fulfill({
          status: baseline.fixtures.query_error_status,
          headers,
          json: { detail: "질의 서비스를 사용할 수 없습니다." },
        });
        return;
      }
      await route.fulfill({
        status: 200,
        headers,
        json: queryResponse(
          payload.question,
          payload.project_id,
          options.largeRows ?? 1,
        ),
      });
      return;
    }
    if (url.pathname === "/api/v1/graph/schema") {
      await route.fulfill({
        status: 200,
        headers,
        json: {
          project_id: url.searchParams.get("project_id") ?? "cip-dmd",
          schema_version: "1.1.0",
          title: "CiP-DMD",
          schema_context: "Cylinder UNDERWENT ProcessRun",
          node_identities: [
            { label: "Cylinder", identity_property: "part_id" },
          ],
          relationship_types: ["UNDERWENT"],
          nodes: [],
          relationships: [],
        },
      });
      return;
    }
    if (url.pathname === "/api/v1/graph/search") {
      await route.fulfill({
        status: 200,
        headers,
        json: {
          label: url.searchParams.get("label") ?? "Cylinder",
          query: url.searchParams.get("query") ?? "",
          identity_property: "part_id",
          nodes: [
            {
              id: "Cylinder:300002",
              labels: ["Cylinder"],
              properties: { part_id: "300002", name: "완제품" },
            },
          ],
          count: 1,
        },
      });
      return;
    }
    if (url.pathname === "/api/v1/graph/subgraph") {
      await route.fulfill({
        status: 200,
        headers,
        json: {
          root: {
            id: "Cylinder:300002",
            labels: ["Cylinder"],
            properties: { part_id: "300002" },
          },
          nodes: [
            {
              id: "Cylinder:300002",
              labels: ["Cylinder"],
              properties: { part_id: "300002" },
            },
            {
              id: "ProcessRun:run-1",
              labels: ["ProcessRun"],
              properties: { run_id: "run-1" },
            },
          ],
          relationships: [
            {
              id: "rel-1",
              type: "UNDERWENT",
              source: "Cylinder:300002",
              target: "ProcessRun:run-1",
              properties: {},
            },
          ],
          node_count: 2,
          relationship_count: 1,
          depth: Number(url.searchParams.get("depth") ?? 2),
          truncated: false,
        },
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

async function expectNoUnnamedInteractiveControls(page: Page) {
  const unnamed = await page.locator("a[href], button, input, select, textarea, summary").evaluateAll(
    (elements) =>
      elements
        .filter((element) => {
          const node = element as HTMLElement;
          return Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
        })
        .filter((element) => {
          const node = element as HTMLElement;
          if (node instanceof HTMLInputElement && node.type === "hidden") return false;
          const ariaLabel = node.getAttribute("aria-label")?.trim();
          const ariaLabelledBy = node.getAttribute("aria-labelledby")?.trim();
          const title = node.getAttribute("title")?.trim();
          const text = node.textContent?.trim();
          const closestLabel = node.closest("label")?.textContent?.trim();
          const id = node.getAttribute("id");
          const explicitLabel = id
            ? document.querySelector(`label[for="${CSS.escape(id)}"]`)?.textContent?.trim()
            : "";
          return !(
            ariaLabel ||
            ariaLabelledBy ||
            title ||
            text ||
            closestLabel ||
            explicitLabel
          );
        })
        .map((element) => element.outerHTML),
  );
  expect(unnamed).toEqual([]);
}

async function expectNoOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - window.innerWidth,
    body: document.body.scrollWidth - window.innerWidth,
  }));
  expect(overflow.document).toBeLessThanOrEqual(0);
  expect(overflow.body).toBeLessThanOrEqual(0);
}

for (const width of baseline.viewport_widths) {
  test(`product routes pass DOM, console, accessibility and ${width}px overflow gate`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const consoleErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => consoleErrors.push(error.message));
    await mockProductApi(page);

    for (const route of baseline.required_product_routes) {
      await page.goto(route.path);
      await expect(page.getByRole("heading", { level: 1, name: route.heading }))
        .toBeVisible();
      await expect(page.locator("main")).not.toBeEmpty();
      const bodyText = await page.locator("main").innerText();
      expect(bodyText.trim().length).toBeGreaterThan(20);
      for (const forbidden of baseline.deployment_forbidden_copy) {
        expect(bodyText).not.toContain(forbidden);
      }
      await expectNoUnnamedInteractiveControls(page);
      await expectNoOverflow(page);
    }
    expect(consoleErrors).toEqual([]);
  });
}

test("all visible product links click to a non-empty destination", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockProductApi(page);
  await page.context().route("https://github.com/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<main><h1>FactoryGraph repository</h1><p>External project destination.</p></main>",
    });
  });
  const sources = baseline.required_product_routes.map((route) => route.path);
  const audited = new Set<string>();

  for (const source of sources) {
    await page.goto(source);
    const links = await page.locator("a[href]").evaluateAll((elements) =>
      elements
        .filter((element) => {
          const node = element as HTMLElement;
          return Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
        })
        .map((element) => ({
          href: element.getAttribute("href") ?? "",
          target: element.getAttribute("target") ?? "",
          download: element.hasAttribute("download"),
        })),
    );
    for (const link of links) {
      if (!link.href || link.download || link.href.startsWith("#")) continue;
      const destination = new URL(link.href, APP_ORIGIN);
      expect(["http:", "https:"]).toContain(destination.protocol);
      const key = `${source} -> ${link.href}`;
      if (audited.has(key)) continue;
      audited.add(key);
      await page.goto(source);
      const locator = page
        .locator(`a[href=${JSON.stringify(link.href)}]`)
        .filter({ visible: true })
        .first();
      await expect(locator).toBeVisible();

      if (link.target === "_blank") {
        const popupPromise = page.waitForEvent("popup");
        await locator.click();
        const popup = await popupPromise;
        await expect(popup.locator("body")).toContainText(
          "External project destination.",
        );
        await popup.close();
        continue;
      }

      await locator.click();
      if (destination.origin === APP_ORIGIN) {
        await expect(page.locator("main")).not.toBeEmpty();
        expect((await page.locator("main").innerText()).trim().length)
          .toBeGreaterThan(20);
      } else {
        await expect(page).toHaveURL(destination.href);
        await expect(page.locator("body")).toContainText("Internal Console", {
          timeout: 15_000,
        });
      }
    }
  }

  expect(audited.size).toBeGreaterThanOrEqual(20);
});

test("keyboard entry exposes skip link and visible focus", async ({ page }) => {
  await mockProductApi(page);
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "본문으로 건너뛰기" });
  await expect(skipLink).toBeFocused();
  const outline = await skipLink.evaluate((element) => {
    const style = window.getComputedStyle(element);
    return { style: style.outlineStyle, width: style.outlineWidth };
  });
  expect(outline.style).not.toBe("none");
  expect(outline.width).not.toBe("0px");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main-content$/);
});

test("LAN HTTP query works without crypto.randomUUID", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window.crypto, "randomUUID", {
      configurable: true,
      value: undefined,
    });
  });
  await mockProductApi(page);
  await page.goto("/query?project_id=cip-dmd");
  const question = "완제품 300002의 구성품을 보여줘.";
  await page.getByLabel("제조 관계 질문").fill(question);
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(page.getByText("자동화된 질의 결과입니다.")).toBeVisible();
  await expect(page.getByText("crypto.randomUUID", { exact: false })).toHaveCount(0);
  await page.getByRole("link", { name: "저장된 기록 보기" }).click();
  await expect(page.getByRole("button", { name: question })).toBeVisible();
});

test("document-only query opens citation evidence and survives History", async ({
  page,
}) => {
  await mockProductApi(page);
  await page.goto("/query?project_id=cip-dmd");
  const question = "압력검사 실패 대응 절차를 SOP에서 알려줘.";
  await page.getByLabel("제조 관계 질문").fill(question);
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(
    page.getByRole("tab", { name: "문서", selected: true }),
  ).toBeVisible();
  await expect(page.getByText("제조 품질검사 SOP")).toBeVisible();
  await expect(
    page.getByText("quality-inspection-sop@1.0:p1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("압력검사 실패 시 상류 공정과 구성품을 확인합니다.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("실행된 Cypher가 없습니다.")).toHaveCount(0);

  await page.getByRole("link", { name: "저장된 기록 보기" }).click();
  await expect(page.getByRole("button", { name: question })).toBeVisible();
  await page.getByRole("link", { name: "다시 열기" }).click();
  await expect(
    page.getByRole("tab", { name: "문서", selected: true }),
  ).toBeVisible();
  await expect(
    page.getByText("quality-inspection-sop@1.0:p1", { exact: true }),
  ).toBeVisible();
});

test("short mobile viewport keeps the header drawer attached to the viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 404, height: 140 });
  await mockProductApi(page);
  await page.goto("/query?project_id=cip-dmd");
  await page.getByRole("button", { name: "메뉴 열기" }).click();
  const navigation = page.locator("#primary-navigation");
  await expect(navigation).toBeVisible();
  const geometry = await navigation.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const point = document.elementFromPoint(
      window.innerWidth - 8,
      window.innerHeight - 8,
    );
    return {
      top: rect.top,
      bottom: rect.bottom,
      height: rect.height,
      viewportHeight: window.innerHeight,
      coversBottom: element.contains(point),
      scrollable: element.scrollHeight > element.clientHeight,
    };
  });
  expect(geometry.top).toBe(64);
  expect(geometry.bottom).toBe(geometry.viewportHeight);
  expect(geometry.height).toBe(geometry.viewportHeight - 64);
  expect(geometry.coversBottom).toBe(true);
  expect(geometry.scrollable).toBe(true);
});

test("long project name and empty registry remain usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockProductApi(page, { projects: [longProject] });
  await page.goto("/query?project_id=long-project");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: `${baseline.fixtures.long_project_name}에 질문하세요.`,
    }),
  ).toBeVisible();
  await expectNoOverflow(page);

  await page.unroute(`${API_ORIGIN}/api/v1/**`);
  await mockProductApi(page, { projects: [] });
  await page.goto("/projects");
  await expect(page.getByText("0 projects", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "새 프로젝트 만들기" })).toBeVisible();
  await expectNoUnnamedInteractiveControls(page);
  await expectNoOverflow(page);
});

test("large results, Evidence, Graph, History and write blocking stay intact", async ({
  page,
}) => {
  const api = await mockProductApi(page, {
    largeRows: baseline.fixtures.large_result_rows,
  });
  await page.goto("/query?project_id=cip-dmd");

  await page.getByRole("button", { name: /제품 Genealogy/ }).click();
  const composer = page.getByLabel("제조 관계 질문");
  await expect(composer).not.toHaveValue("");
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(
    page.locator("#query-evidence").getByText(
      `결과 ${baseline.fixtures.large_result_rows}건`,
      { exact: true },
    ),
  ).toBeVisible();
  await expect(composer).toHaveValue("");
  await expect(page.getByRole("tab", { name: "결과", exact: true })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("tab", { name: "그래프" }).click();
  await expect(page.getByText("노드 2 · 관계 1", { exact: false })).toBeVisible();

  await page.getByRole("link", { name: "저장된 기록 보기" }).click();
  await expect(page).toHaveURL("/history?project_id=cip-dmd");
  await page.getByRole("link", { name: "다시 열기" }).click();
  await expect(page).toHaveURL(/\/query\?project_id=cip-dmd&conversation=/);
  await expect(page.getByText("자동화된 질의 결과입니다.")).toBeVisible();

  await composer.fill("압력검사 실패 데이터를 전부 삭제해줘.");
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(page.getByText("조회 전용 서비스에서 변경 요청을 차단했습니다.")).toBeVisible();
  expect(api.queryRequests.filter((question) => question.includes("삭제"))).toHaveLength(1);
});

test("Graph Explorer completes a visible search and path exploration", async ({
  page,
}) => {
  await mockProductApi(page);
  await page.goto("/graph?project_id=cip-dmd");
  await page.getByLabel("노드 검색어").fill("3000");
  await page.getByRole("button", { name: "노드 검색" }).click();
  await expect(page.getByText("1개 검색 결과")).toBeVisible();
  await page.getByRole("button", { name: /Cylinder.*300002/ }).click();
  await expect(page.getByText("2 nodes", { exact: false })).toBeVisible();
  await expect(page.getByText("1 relationships", { exact: false })).toBeVisible();
});

test("query service error is recoverable without losing context", async ({ page }) => {
  await mockProductApi(page, { failQuery: true });
  await page.goto("/query?project_id=cip-dmd");
  const question = "완제품 300002의 구성품을 보여줘.";
  await page.getByLabel("제조 관계 질문").fill(question);
  await page.getByRole("button", { name: "질문 전송" }).click();
  await expect(page.getByText("API 연결 또는 질의 처리 실패")).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 시도" })).toBeVisible();
  await expect(page.getByText(question)).toBeVisible();
});
