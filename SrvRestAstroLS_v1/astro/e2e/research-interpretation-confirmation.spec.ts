import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

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

/**
 * Primary UX (ADR-006): the composer sends the question directly; there is no
 * interpretation confirmation gate. These tests validate the analysis
 * contracts that remain in the legacy pipeline: determinism, idempotency,
 * abort semantics and RTL rendering.
 */
async function ask(page: Page, question: string) {
  const pending = page.waitForResponse(
    (response) => response.url().endsWith(endpoint)
      && response.request().method() === "POST"
      && !response.request().postDataJSON()?.phase,
  );
  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click();
  const response = await pending;
  expect(response.status()).toBe(200);
  await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 120_000 });
  return response.json();
}

function disableAi(page: Page) {
  return page.route(`**${endpoint}`, async (route) => {
    const payload = route.request().postDataJSON();
    if (payload && !payload.phase) {
      await route.continue({
        postData: JSON.stringify({ ...payload, ai: { ...payload.ai, enabled: false } }),
      });
      return;
    }
    await route.continue();
  });
}

test("a single analysis resolves and the session survives reload", async ({ page }) => {
  test.setTimeout(120_000);
  await disableAi(page);
  await login(page);
  const body = await ask(page, "tisha beav");
  expect(body.hits.length).toBeGreaterThan(0);
  await page.screenshot({ path: path.join(screenshots, "single-analysis.png"), fullPage: true });

  // The session (not the in-memory turn) persists across a reload.
  await page.reload();
  await expect(page).toHaveURL(/\/research\/?$/);
  await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 20_000 });
});

test("deterministic fallback stays grounded and does not surface ValidationError", async ({ page }) => {
  test.setTimeout(120_000);
  await disableAi(page);
  await login(page);
  const body = await ask(page, "tisha beav");
  expect(body.hits.length).toBeGreaterThan(0);
  await expect(page.getByText(/ValidationError/)).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshots, "fallback-analysis.png"), fullPage: true });
});

test("new research aborts an in-flight analysis and ignores its late result", async ({ page }) => {
  await page.route(`**${endpoint}`, async (route) => {
    const payload = route.request().postDataJSON();
    if (payload && !payload.phase) {
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
      return;
    }
    await route.continue();
  });
  await login(page);
  await page.getByTestId("research-question").fill("tisha beav");
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("research-submit")).toHaveAttribute("aria-disabled", "true");
  await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
  await expect(page.getByRole("heading", { name: "¿Qué desea investigar?" })).toBeVisible();
  await page.waitForTimeout(1700);
  await expect(page.getByText("late result")).toHaveCount(0);
  await expect(page.getByTestId("research-question")).toBeEnabled();
});

test("Hebrew query renders RTL results on mobile without overflow", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const pending = page.waitForResponse(
    (response) => response.url().endsWith(endpoint)
      && response.request().method() === "POST"
      && !response.request().postDataJSON()?.phase,
  );
  await page.getByTestId("research-question").fill("איפה מופיע המושג עקרב");
  await page.getByTestId("research-submit").click();
  const response = await pending;
  expect(response.status()).toBe(200);
  await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 120_000 });
  const question = page.getByRole("heading", { level: 2 }).first();
  await expect(question).toHaveAttribute("dir", "rtl");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: path.join(screenshots, "rtl.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "mobile.png"), fullPage: true });
});
