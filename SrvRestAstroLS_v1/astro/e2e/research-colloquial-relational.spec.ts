import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page, type Request } from "@playwright/test";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
const endpoint = "/library/investigative-qa/v1";
const screenshots = path.resolve(
  import.meta.dirname,
  "../../../data/reports/breslov/2026-07-26-colloquial-relational-interpretation/screenshots",
);
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

test("colloquial Azamra relation remains pending until one real analysis", async ({ page }) => {
  test.setTimeout(120_000);
  const phases: string[] = [];
  page.on("request", (request) => {
    const value = phase(request);
    if (value) phases.push(value);
  });
  await login(page);
  await page.getByTestId("research-question").fill("azamra la relaciones que tiene");
  await page.getByTestId("research-submit").click();

  const card = page.getByTestId("interpretation-card");
  await expect(card).toContainText(
    "Interpreté que desea investigar con qué conceptos se relaciona Azamra.",
    { timeout: 30_000 },
  );
  await expect(card).not.toContainText("investigar «azamra la relaciones que tiene»");
  await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
    "Analizar",
    "Modificar",
  ]);
  await expect(page.getByTestId("pending-evidence-panel")).toHaveText(
    "La evidencia verificable aparecerá después del análisis.",
  );
  await expect(page.getByText("Seleccioná un turno para revisar sus fuentes y páginas.")).toHaveCount(0);
  await expect(page.getByText("Resultados por obra")).toHaveCount(0);
  expect(phases).toEqual(["interpret"]);

  await page.screenshot({ path: path.join(screenshots, "correct-interpretation.png"), fullPage: true });
  await page.getByTestId("interpretation-actions").screenshot({
    path: path.join(screenshots, "exact-two-actions.png"),
  });
  await page.getByTestId("pending-evidence-panel").screenshot({
    path: path.join(screenshots, "pending-evidence-panel.png"),
  });

  const analysisResponse = page.waitForResponse((response) =>
    response.url().endsWith(endpoint) && phase(response.request()) === "analyze"
  );
  await page.getByTestId("interpretation-analyze").click();
  await expect(page.getByText("Analizando…")).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, "analyzing.png"), fullPage: true });
  const response = await analysisResponse;
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.intent).toBe("concept_cooccurrence");
  expect(body.interpretation.query_subjects).toEqual(
    expect.arrayContaining([expect.objectContaining({ raw: "azamra", canonical: "Azamra" })]),
  );
  expect(phases).toEqual(["interpret", "analyze"]);
  await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("[data-evidence-id]")).not.toHaveCount(0);
  await page.screenshot({ path: path.join(screenshots, "relational-result.png"), fullPage: true });
});

test("modify reinterprets a binary relation without analyzing the old subject", async ({ page }) => {
  test.setTimeout(120_000);
  const phases: string[] = [];
  page.on("request", (request) => {
    const value = phase(request);
    if (value) phases.push(value);
  });
  await login(page);
  await page.getByTestId("research-question").fill("azamra la relaciones que tiene");
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("interpretation-card")).toContainText("Azamra", { timeout: 30_000 });

  await page.getByTestId("interpretation-modify").click();
  await expect(page.getByTestId("interpretation-editor")).toBeFocused();
  await page.screenshot({ path: path.join(screenshots, "modify-editor.png"), fullPage: true });
  await page.getByTestId("interpretation-editor").fill("relación entre Azamra y alegría");
  await page.getByTestId("interpretation-editor").press("Enter");
  await expect(page.getByTestId("interpretation-card")).toContainText(
    "Interpreté que desea investigar la relación entre «Azamra» y «alegría».",
    { timeout: 30_000 },
  );
  await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
    "Analizar",
    "Modificar",
  ]);
  await expect(page.getByTestId("pending-evidence-panel")).toBeVisible();
  expect(phases).toEqual(["interpret", "interpret"]);
  await page.screenshot({ path: path.join(screenshots, "modified-interpretation.png"), fullPage: true });

  await page.getByTestId("interpretation-analyze").click();
  await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 60_000 });
  expect(phases).toEqual(["interpret", "interpret", "analyze"]);
});

test("disabled AI uses the same relational fallback and remains confirmable", async ({ page }) => {
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
  await page.getByTestId("research-question").fill("azamra la relaciones que tiene");
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("interpretation-card")).toContainText(
    "Interpreté que desea investigar con qué conceptos se relaciona Azamra.",
    { timeout: 30_000 },
  );
  await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
    "Analizar",
    "Modificar",
  ]);
  await expect(page.getByText(/ValidationError/)).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshots, "before-generic-echo.png"), fullPage: true });
  await page.getByTestId("interpretation-analyze").click();
  await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 60_000 });
});

test("Hebrew relational confirmation remains RTL and usable on mobile", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.getByTestId("research-question").fill("עם אילו מושגים קשור אזמרה");
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("interpretation-card")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("interpretation-actions").getByRole("button")).toHaveText([
    "Analizar",
    "Modificar",
  ]);
  await expect(page.getByTestId("pending-evidence-panel")).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, "mobile.png"), fullPage: true });
  await page.getByTestId("interpretation-card").screenshot({
    path: path.join(screenshots, "rtl.png"),
  });
});

test("real UI keeps focal and modify flows singular twenty of twenty", async ({ page }) => {
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

  for (let iteration = 0; iteration < 20; iteration += 1) {
    if (iteration > 0) {
      await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
    }
    let offset = phases.length;
    await page.getByTestId("research-question").fill("azamra la relaciones que tiene");
    await page.getByTestId("research-submit").click();
    await expect(page.getByTestId("interpretation-card")).toContainText(
      "con qué conceptos se relaciona Azamra",
    );
    await expect(page.getByTestId("pending-evidence-panel")).toBeVisible();
    await page.getByTestId("interpretation-analyze").click();
    await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 60_000 });
    expect(phases.slice(offset)).toEqual(["interpret", "analyze"]);

    await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
    offset = phases.length;
    await page.getByTestId("research-question").fill("azamra la relaciones que tiene");
    await page.getByTestId("research-submit").click();
    await page.getByTestId("interpretation-modify").click();
    await page.getByTestId("interpretation-editor").fill("relación entre Azamra y alegría");
    await page.getByTestId("interpretation-editor").press("Enter");
    await expect(page.getByTestId("interpretation-card")).toContainText(
      "la relación entre «Azamra» y «alegría»",
    );
    await expect(page.getByTestId("pending-evidence-panel")).toBeVisible();
    await page.getByTestId("interpretation-analyze").click();
    await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 60_000 });
    expect(phases.slice(offset)).toEqual(["interpret", "interpret", "analyze"]);
  }
});
