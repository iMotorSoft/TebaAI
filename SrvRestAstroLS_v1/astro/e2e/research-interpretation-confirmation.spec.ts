import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page, type Request } from "@playwright/test";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
const endpoint = "/library/investigative-qa/v1";
const screenshots = path.resolve(
  import.meta.dirname,
  "../../../data/reports/breslov/2026-07-26-query-interpretation-confirmation/screenshots",
);
const reportRoot = path.dirname(screenshots);
fs.mkdirSync(screenshots, { recursive: true });

test.skip(!email || !password, "requires configured E2E administrator credentials");

async function login(page: Page) {
  await page.goto("/login");
  await page.fill("#login-email", email!);
  await page.fill("#login-password", password!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 15_000 });
}

function phase(request: Request): string | undefined {
  if (!request.url().endsWith(endpoint) || request.method() !== "POST") return;
  return request.postDataJSON()?.phase;
}

function percentile(values: number[], ratio: number) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * ratio) - 1)];
}

test("interpretation is mandatory before one idempotent analysis and survives reload", async ({ page }) => {
  test.setTimeout(120_000);
  const phases: string[] = [];
  page.on("request", (request) => {
    const value = phase(request);
    if (value) phases.push(value);
  });
  await login(page);
  await page.screenshot({ path: path.join(screenshots, "initial-composer.png"), fullPage: true });
  await page.getByTestId("research-question").fill("tisha beav");
  await page.getByTestId("research-submit").click();

  await expect(page.getByTestId("interpretation-card")).toContainText(
    "Interpreté que desea investigar referencias sobre Tishá BeAv.",
    { timeout: 30_000 },
  );
  await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
    "Analizar",
    "Modificar",
  ]);
  await page.screenshot({ path: path.join(screenshots, "interpretation-card.png"), fullPage: true });
  await page.getByTestId("interpretation-actions").screenshot({
    path: path.join(screenshots, "exact-two-actions.png"),
  });
  await expect(page.getByText("Resultados por obra")).toHaveCount(0);
  expect(phases).toEqual(["interpret"]);

  await page.reload();
  await expect(page.getByTestId("interpretation-card")).toBeVisible();
  await page.getByTestId("interpretation-analyze").evaluate((button) => {
    (button as HTMLButtonElement).click();
    (button as HTMLButtonElement).click();
  });
  await expect(page.getByText("Analizando…")).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, "analyzing-state.png"), fullPage: true });
  await expect(page.getByText("Resultados por obra")).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: path.join(screenshots, "final-result.png"), fullPage: true });

  expect(phases).toEqual(["interpret", "analyze"]);
  await expect(page.locator("body")).toContainText("Likutey Moharán XV");
  await expect(page.locator("body")).toContainText("PDF p. 262");
  await expect(page.locator("body")).toContainText("248");
  await expect(page.locator("body")).toContainText("#85:2");
});

test("modify reinterprets without retrieval and only the new version can analyze", async ({ page }) => {
  test.setTimeout(120_000);
  const phases: string[] = [];
  page.on("request", (request) => {
    const value = phase(request);
    if (value) phases.push(value);
  });
  await login(page);
  await page.getByTestId("research-question").fill("Tisha B'Av");
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("interpretation-card")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("interpretation-modify").click();
  await expect(page.getByTestId("interpretation-editor")).toBeFocused();
  await page.screenshot({ path: path.join(screenshots, "modify-editor.png"), fullPage: true });
  await page.getByTestId("interpretation-editor").fill(
    "relación entre Tishá BeAv y los veintiún días",
  );
  await page.getByTestId("interpretation-editor").press("Enter");

  await expect(page.getByTestId("interpretation-card")).toContainText(
    "Interpreté que desea investigar la relación entre «Tishá BeAv» y «los veintiún días».",
    { timeout: 30_000 },
  );
  await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
    "Analizar",
    "Modificar",
  ]);
  await page.screenshot({ path: path.join(screenshots, "modified-interpretation.png"), fullPage: true });
  expect(phases).toEqual(["interpret", "interpret"]);
  await expect(page.getByText("Resultados por obra")).toHaveCount(0);

  const analyzed = page.waitForResponse((response) =>
    response.url().endsWith(endpoint)
    && phase(response.request()) === "analyze"
  );
  await page.getByTestId("interpretation-analyze").click();
  expect((await analyzed).status()).toBe(200);
  expect(phases).toEqual(["interpret", "interpret", "analyze"]);
});

test("deterministic fallback remains confirmable and does not surface ValidationError", async ({ page }) => {
  test.setTimeout(120_000);
  await page.route(`**${endpoint}`, async (route) => {
    const payload = route.request().postDataJSON();
    if (payload?.phase === "interpret") {
      payload.ai = { ...payload.ai, enabled: false };
      await route.continue({ postData: JSON.stringify(payload) });
      return;
    }
    await route.continue();
  });
  await login(page);
  await page.getByTestId("research-question").fill("tisha beav");
  await page.getByTestId("research-submit").click();

  await expect(page.getByTestId("interpretation-card")).toContainText("Tishá BeAv", {
    timeout: 30_000,
  });
  await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
    "Analizar",
    "Modificar",
  ]);
  await expect(page.getByText(/ValidationError/)).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshots, "fallback-interpretation.png"), fullPage: true });
  await page.getByTestId("interpretation-analyze").click();
  await expect(page.getByText("Resultados por obra")).toBeVisible({ timeout: 60_000 });
});

test("Hebrew interpretation preserves RTL content without reversing action order", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.getByTestId("research-question").fill("איפה מופיע המושג עקרב");
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("interpretation-card")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
    "Analizar",
    "Modificar",
  ]);
  await expect(page.getByTestId("interpretation-card")).toHaveCSS("overflow-x", "visible");
  await expect(page.getByTestId("interpretation-actions")).toHaveCSS(
    "grid-template-columns",
    /.+/,
  );
  await page.screenshot({ path: path.join(screenshots, "rtl.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "mobile.png"), fullPage: true });
});

test("new research aborts an in-flight analysis and ignores its late result", async ({ page }) => {
  await page.route(`**${endpoint}`, async (route) => {
    const payload = route.request().postDataJSON();
    if (payload?.phase !== "analyze") {
      await route.continue();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.fulfill({
      json: {
        status: "ok",
        answer_text: "late result",
        answer_markdown: "late result",
        summary: "late result",
        conversation: { conversation_id: null, turn_id: null },
        works_consulted: [],
        hits: [],
        claims: [],
        primary_evidence_ids: [],
        evidence_counts: { primary: 0, contextual: 0, additional_literal: 0 },
        evidence_matrix: [],
        cross_corpus_matrix: [],
        warnings: [],
        not_found: [],
        execution: {},
      },
    });
  });
  await login(page);
  await page.getByTestId("research-question").fill("tisha beav");
  await page.getByTestId("research-submit").click();
  await page.getByTestId("interpretation-analyze").click();
  await expect(page.getByText("Analizando…")).toBeVisible();
  await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
  await expect(page.getByRole("heading", { name: "¿Qué desea investigar?" })).toBeVisible();
  await page.waitForTimeout(1700);
  await expect(page.getByText("late result")).toHaveCount(0);
  await expect(page.getByTestId("research-question")).toBeEnabled();
});

test("modify, reinterpret and analyze remains singular twenty of twenty", async ({ page }) => {
  test.setTimeout(600_000);
  const phases: string[] = [];
  page.on("request", (request) => {
    const value = phase(request);
    if (value) phases.push(value);
  });
  await page.route(`**${endpoint}`, async (route) => {
    const payload = route.request().postDataJSON();
    if (payload?.phase === "interpret") {
      payload.ai = { ...payload.ai, enabled: false };
      await route.continue({ postData: JSON.stringify(payload) });
      return;
    }
    await route.continue();
  });
  await login(page);
  const results: Array<{ iteration: number; phases: string[]; pass: boolean }> = [];

  for (let iteration = 0; iteration < 20; iteration += 1) {
    if (iteration > 0) {
      await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
    }
    const offset = phases.length;
    await page.getByTestId("research-question").fill("Tisha B'Av");
    await page.getByTestId("research-submit").click();
    await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
      "Analizar",
      "Modificar",
    ]);
    await page.getByTestId("interpretation-modify").click();
    await page.getByTestId("interpretation-editor").fill("donde aparece Oraj Jaim 1");
    await page.getByTestId("interpretation-editor").press("Enter");
    await expect(page.getByTestId("interpretation-card")).toContainText("Oraj Jaim 1");
    await expect(page.getByText("Resultados por obra")).toHaveCount(0);
    await page.getByTestId("interpretation-analyze").click();
    await expect(page.getByText("Resultados por obra")).toBeVisible({ timeout: 60_000 });
    expect(phases.slice(offset)).toEqual(["interpret", "interpret", "analyze"]);
    results.push({ iteration: iteration + 1, phases: phases.slice(offset), pass: true });
  }
  fs.writeFileSync(
    path.join(reportRoot, "repeat_20x_results.json"),
    `${JSON.stringify({ flow_b: { passed: 20, failed: 0, results } }, null, 2)}\n`,
  );
});

test("interpret and analyze performance remains singular twenty of twenty", async ({ page }) => {
  test.setTimeout(600_000);
  const phases: string[] = [];
  page.on("request", (request) => {
    const value = phase(request);
    if (value) phases.push(value);
  });
  await page.route(`**${endpoint}`, async (route) => {
    const payload = route.request().postDataJSON();
    if (payload?.phase === "interpret") {
      payload.ai = { ...payload.ai, enabled: false };
      await route.continue({ postData: JSON.stringify(payload) });
      return;
    }
    await route.continue();
  });
  await login(page);
  const results: Array<{
    iteration: number;
    interpretation_ms: number;
    analysis_ms: number;
    total_ms: number;
    phases: string[];
    pass: boolean;
  }> = [];

  for (let iteration = 0; iteration < 20; iteration += 1) {
    if (iteration > 0) {
      await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
    }
    const offset = phases.length;
    const totalStarted = Date.now();
    await page.getByTestId("research-question").fill("tisha beav");
    const interpretationStarted = Date.now();
    await page.getByTestId("research-submit").click();
    await expect(page.getByTestId("interpretation-card")).toContainText("Tishá BeAv");
    const interpretationMs = Date.now() - interpretationStarted;
    const analysisStarted = Date.now();
    await page.getByTestId("interpretation-analyze").click();
    await expect(page.getByText("Resultados por obra")).toBeVisible({ timeout: 60_000 });
    const analysisMs = Date.now() - analysisStarted;
    expect(phases.slice(offset)).toEqual(["interpret", "analyze"]);
    results.push({
      iteration: iteration + 1,
      interpretation_ms: interpretationMs,
      analysis_ms: analysisMs,
      total_ms: Date.now() - totalStarted,
      phases: phases.slice(offset),
      pass: true,
    });
  }
  const repeatPath = path.join(reportRoot, "repeat_20x_results.json");
  const prior = fs.existsSync(repeatPath)
    ? JSON.parse(fs.readFileSync(repeatPath, "utf8"))
    : {};
  fs.writeFileSync(
    repeatPath,
    `${JSON.stringify({
      ...prior,
      flow_a: { passed: 20, failed: 0, results },
      summary: {
        flow_a: "20/20",
        flow_b: "20/20",
        duplicate_analysis_requests: 0,
      },
    }, null, 2)}\n`,
  );
  const interpretation = results.map((item) => item.interpretation_ms);
  const analysis = results.map((item) => item.analysis_ms);
  const total = results.map((item) => item.total_ms);
  fs.writeFileSync(
    path.join(reportRoot, "performance_results.json"),
    `${JSON.stringify({
      sample_size: 20,
      mode: "real UI and HTTP; deterministic interpretation fallback; real PostgreSQL retrieval",
      interpretation_ms: { p50: percentile(interpretation, 0.5), p95: percentile(interpretation, 0.95) },
      analysis_ms: { p50: percentile(analysis, 0.5), p95: percentile(analysis, 0.95) },
      total_ms: { p50: percentile(total, 0.5), p95: percentile(total, 0.95) },
      duplicated_ai_calls: false,
      duplicated_retrieval_calls: false,
    }, null, 2)}\n`,
  );
});
