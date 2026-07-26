import fs from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
const reportRoot = path.resolve(
  import.meta.dirname,
  "../../../data/reports/breslov/2026-07-21-literal-evidence-final-gates",
);
const screenshots = path.join(reportRoot, "screenshots");

async function login(page: Page, diagnostics: { consoleErrors: string[]; pageErrors: string[] }) {
  await page.goto("/login");
  await expect(page.locator("astro-island:not([ssr])")).toBeAttached();
  await page.fill("#login-email", email!);
  await page.fill("#login-password", password!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible().catch(async (error) => {
    throw new Error(`${error.message}\nBrowser diagnostics: ${JSON.stringify(diagnostics)}`);
  });
}

async function ask(page: Page, question: string) {
  const pending = page.waitForResponse(
    (response) => response.url().endsWith("/library/investigative-qa/v1")
      && response.request().method() === "POST" && response.request().postDataJSON()?.phase === "analyze",
  );
  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click();
  const response = await pending;
  expect(response.status()).toBe(200);
  return response.json();
}

test.skip(!email || !password, "requires configured E2E administrator credentials");

test("real literal evidence presentation remains clean and auditable", async ({ page }) => {
  test.setTimeout(300_000);
  fs.mkdirSync(screenshots, { recursive: true });
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await login(page, { consoleErrors, pageErrors });
  const payload = await ask(page, "servir a HaShem por la noche");
  const primary = payload.hits.find((hit: any) => payload.primary_evidence_ids.includes(hit.hit_id));

  expect(payload.intent).toBe("literal_lookup");
  expect(primary).toMatchObject({
    evidence_id: "lh-37c67830012c",
    work_code: "lh",
    physical_pdf_page: 137,
    literal_match_kind: "exact_phrase",
    snippet_sanitized: true,
    document_id: "37b5842d-517d-49d1-bab0-3584f409f355",
    source_layer: "unknown",
    source_layer_confidence: "low",
    source_layer_rationale: "page_literal_only_without_validated_zone",
    author_quote_status: "not_confirmed",
  });
  expect(primary.display_snippet).toContain("servir a HaShem por la noche");
  expect(primary.display_snippet).not.toMatch(/[\u0080-\u009f]/u);
  expect(primary.display_snippet).not.toContain("<#>");
  expect(primary.raw_snippet).not.toBe(primary.display_snippet);

  const summaryCount = await page.getByText("Síntesis investigativa", { exact: true }).count();
  const visibleText = await page.locator("body").innerText();
  const duplicateSnippetCount = await page.locator("blockquote").filter({ hasText: "servir a HaShem por la noche" }).count();
  fs.writeFileSync(path.join(reportRoot, "ui-reproduction-runtime.json"), `${JSON.stringify({
    intent: payload.intent,
    evidence_id: primary.evidence_id,
    document_id: primary.document_id,
    physical_pdf_page: primary.physical_pdf_page,
    source_layer: primary.source_layer,
    source_layer_confidence: primary.source_layer_confidence,
    search_record_type: primary.search_record_type,
    zone_type: primary.zone_type,
    note_number: primary.note_number,
    summary_count: summaryCount,
    duplicate_snippet_count: duplicateSnippetCount,
    warnings: payload.warnings,
    console_errors: consoleErrors,
    page_errors: pageErrors,
  }, null, 2)}\n`);
  expect(summaryCount).toBe(1);
  expect(duplicateSnippetCount).toBe(1);
  expect(visibleText).not.toMatch(/[\u0080-\u009f]/u);
  expect(visibleText).not.toContain("<#>");
  await expect(page.getByText("1 evidencia principal", { exact: true })).toBeVisible();
  await expect(page.getByText("1 relación contextual", { exact: true })).toBeVisible();
  await expect(page.getByText("No confirmada como formulación textual del autor original", { exact: true })).toHaveCount(1);
  const warning = "El fragmento visible fue limpiado de artefactos de extracción PDF; el texto fuente original se conserva para auditoría.";
  await expect(page.getByText(warning, { exact: true })).toHaveCount(1);
  await page.getByText("Matriz de evidencia", { exact: true }).click();
  await expect(page.locator(".matrix-table .matrix-row")).toHaveCount(2);
  await expect(page.locator(".matrix-table .matrix-row").nth(1)).toContainText("Likutey Halajot");

  for (const name of ["single-summary", "clean-snippet", "source-layer", "author-attribution", "matrix"]) {
    await page.screenshot({ path: path.join(screenshots, `${name}.png`), fullPage: true });
  }

  const followup = await ask(page, "¿es texto de Rabí Natán o comentario editorial?");
  const followupPrimary = followup.hits.find((hit: any) => followup.primary_evidence_ids.includes(hit.hit_id));
  expect(followup).toMatchObject({
    intent: "source_layer_question",
    target_evidence_id: "lh-37c67830012c",
    same_primary_evidence: true,
  });
  expect(followupPrimary).toMatchObject({
    evidence_id: primary.evidence_id,
    work_code: "lh",
    physical_pdf_page: 137,
    source_layer: "unknown",
    source_layer_confidence: "low",
    author_quote_status: "not_confirmed",
  });
  expect(followup.claims[0].text).toContain("No confirmado");
  await page.screenshot({ path: path.join(screenshots, "follow-up-editorial.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Fuentes", exact: true }).click();
  await expect(page.locator(".sources.open")).toContainText("PDF p. 137");
  await page.screenshot({ path: path.join(screenshots, "mobile.png"), fullPage: true });
  await page.keyboard.press("Escape");
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter((item) => item.impact === "critical" || item.impact === "serious")).toEqual([]);

  await page.setViewportSize({ width: 1280, height: 720 });
  await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  const hebrew = await ask(page, "תהלתי אחטם לך");
  expect(hebrew.intent).toBe("literal_lookup");
  const hebrewBlock = page.locator('blockquote[lang="he"][dir="rtl"]').first();
  await expect(hebrewBlock).toBeVisible();
  await expect(hebrewBlock).toContainText("תְּהִלָּתִי אֶחְטָם לָךְ");
  await page.screenshot({ path: path.join(screenshots, "rtl.png"), fullPage: true });

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
  await expect(page).toHaveURL(/\/login$/);
});

test("real literal evidence is stable twenty of twenty times", async ({ page }) => {
  test.setTimeout(900_000);
  fs.mkdirSync(reportRoot, { recursive: true });
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await login(page, { consoleErrors, pageErrors });

  const results = [];
  for (let iteration = 1; iteration <= 20; iteration += 1) {
    if (iteration > 1) {
      await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
    }
    const started = Date.now();
    const payload = await ask(page, "servir a HaShem por la noche");
    const primary = payload.hits.find((hit: any) => payload.primary_evidence_ids.includes(hit.hit_id));
    const summaryCount = await page.getByText("Síntesis investigativa", { exact: true }).count();
    const visible = await page.locator("body").innerText();
    expect(payload.intent, `iteration ${iteration}`).toBe("literal_lookup");
    expect(primary, `iteration ${iteration}`).toMatchObject({
      evidence_id: "lh-37c67830012c",
      work_code: "lh",
      physical_pdf_page: 137,
      literal_match_kind: "exact_phrase",
      snippet_sanitized: true,
      source_layer: "unknown",
      source_layer_confidence: "low",
      author_quote_status: "not_confirmed",
    });
    expect(primary.display_snippet, `iteration ${iteration}`).toContain("servir a HaShem por la noche");
    expect(summaryCount, `iteration ${iteration}`).toBe(1);
    expect(visible, `iteration ${iteration}`).not.toMatch(/[\u0080-\u009f]/u);
    expect(visible, `iteration ${iteration}`).not.toContain("<#>");
    results.push({ iteration, duration_ms: Date.now() - started, intent: payload.intent, evidence_id: primary.evidence_id, pdf_page: primary.physical_pdf_page, source_layer: primary.source_layer, source_layer_confidence: primary.source_layer_confidence, author_quote_status: primary.author_quote_status, summary_count: summaryCount, pass: true });
  }
  fs.writeFileSync(path.join(reportRoot, "repeat-20x-ui-runtime.json"), `${JSON.stringify({ total: 20, passed: 20, failed: 0, console_errors: consoleErrors, page_errors: pageErrors, results }, null, 2)}\n`);
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
  await expect(page).toHaveURL(/\/login$/);
});
