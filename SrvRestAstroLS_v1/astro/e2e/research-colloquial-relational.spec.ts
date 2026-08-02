import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
const endpoint = "/library/investigative-qa/v1";
const screenshots = path.resolve(
  import.meta.dirname,
  "../../../data/reports/breslov/2026-07-26-colloquial-relational-interpretation/screenshots",
);
import fs from "node:fs";
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
 * Legacy primary UX (ADR-006): the composer sends the question directly and
 * the workspace renders the grounded answer without an interpretation
 * confirmation gate.
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

test("colloquial Azamra relation resolves with grounded evidence", async ({ page }) => {
  test.setTimeout(300_000);
  await login(page);
  const body = await ask(page, "azamra la relaciones que tiene");
  expect(body).toMatchObject({ pipeline: "simple_rag", research_status: expect.any(String) });
  expect(body.hits.length).toBeGreaterThan(0);
  await expect(page.locator("[data-evidence-id]")).not.toHaveCount(0);
  await page.screenshot({ path: path.join(screenshots, "relational-result.png"), fullPage: true });
});

test("a binary relation query resolves independently on a new turn", async ({ page }) => {
  test.setTimeout(180_000);
  await login(page);
  await ask(page, "relación entre Azamra y alegría");
  await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
  const second = await ask(page, "relación entre Azamra y alegría");
  expect(second.hits.length).toBeGreaterThan(0);
  await page.screenshot({ path: path.join(screenshots, "modified-interpretation.png"), fullPage: true });
});

test("disabled AI keeps the same deterministic fallback grounded", async ({ page }) => {
  test.setTimeout(180_000);
  await page.route(`**${endpoint}`, async (route) => {
    const payload = route.request().postDataJSON();
    if (payload && !payload.phase) {
      await route.continue({
        postData: JSON.stringify({ ...payload, ai: { ...payload.ai, enabled: false } }),
      });
      return;
    }
    await route.continue();
  });
  await login(page);
  const body = await ask(page, "azamra la relaciones que tiene");
  expect(body.hits.length).toBeGreaterThan(0);
  await expect(page.getByText(/ValidationError/)).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshots, "before-generic-echo.png"), fullPage: true });
});

test("Hebrew relational query stays RTL and usable on mobile", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const body = await ask(page, "עם אילו מושגים קשור אזמרה");
  expect(body.hits.length).toBeGreaterThan(0);
  const question = page.getByRole("heading", { level: 2 }).first();
  await expect(question).toHaveAttribute("dir", "rtl");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: path.join(screenshots, "mobile.png"), fullPage: true });
});

test("real UI keeps the focal analysis singular on repeated runs", async ({ page }) => {
  test.setTimeout(300_000);
  await page.route(`**${endpoint}`, async (route) => {
    const payload = route.request().postDataJSON();
    if (payload && !payload.phase) {
      await route.continue({
        postData: JSON.stringify({ ...payload, ai: { ...payload.ai, enabled: false } }),
      });
      return;
    }
    await route.continue();
  });
  await login(page);
  for (let iteration = 0; iteration < 3; iteration += 1) {
    if (iteration > 0) {
      await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
    }
    const body = await ask(page, "azamra la relaciones que tiene");
    expect(body.hits.length).toBeGreaterThan(0);
  }
});
