import fs from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
const reportRoot = path.resolve(
  import.meta.dirname,
  "../../../data/reports/breslov/2026-07-22-named-topic-transliteration",
);
const screenshots = path.join(reportRoot, "screenshots");

async function login(page: Page) {
  await page.goto("/login");
  await expect(page.locator("astro-island:not([ssr])")).toBeAttached();
  await page.fill("#login-email", email!);
  await page.fill("#login-password", password!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible();
}

async function ask(page: Page, question: string) {
  const pending = page.waitForResponse(
    (response) => response.url().endsWith("/library/investigative-qa/v1")
      && response.request().method() === "POST",
  );
  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click();
  const response = await pending;
  expect(response.status()).toBe(200);
  return response.json();
}

function assertTishaPayload(payload: any, raw: string) {
  expect(payload.status).toBe("ok");
  expect(payload.intent).toBe("concept_lookup");
  expect(payload.query_understanding).toMatchObject({
    subject_raw: raw,
    subject_canonical: "Tishá BeAv",
    subject_type: "named_topic",
    operation: "find_named_topic",
  });
  expect(payload.named_topic).toMatchObject({
    canonical_id: "jewish_calendar.tisha_beav",
    canonical_label: "Tishá BeAv",
  });
  const primary = payload.hits.find((hit: any) => payload.primary_evidence_ids.includes(hit.hit_id));
  expect(primary).toMatchObject({
    work_title: "Likutey Moharán XV KDP",
    pdf_page: 262,
    printed_page: 248,
    literal_match_kind: expect.stringMatching(/^named_topic_(?:exact|normalized|alias)$/),
    direct_support: true,
    match_strength: "strong",
    evidence_strength: "strong",
    single_term: false,
  });
  expect(primary.section).toContain("#85:2");
  expect(primary.snippet).toContain("ayuno de Tisha beAv");
  expect(payload.warnings.join(" ")).not.toContain("ValidationError");
  return primary;
}

test.skip(!email || !password, "requires configured E2E administrator credentials");

test("real named-topic aliases preserve the full subject and strong LM XV evidence", async ({ page }) => {
  test.setTimeout(240_000);
  fs.mkdirSync(screenshots, { recursive: true });
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await login(page);

  const fallbackFriendly = await ask(page, "tisha beav");
  assertTishaPayload(fallbackFriendly, "tisha beav");
  await expect(page.locator(".query-interpretation").last()).toContainText("Interpreté la consulta como: Tishá BeAv");
  await expect(page.locator("body")).not.toContainText("Busqué el concepto: tisha");
  await expect(page.locator("body")).not.toContainText("relación solicitada");
  await page.screenshot({ path: path.join(screenshots, "canonical-topic.png"), fullPage: true });

  await page.getByRole("button", { name: /Ver fuente de:/ }).first().click();
  await expect(page.locator(".source-detail")).toContainText("Likutey Moharán XV KDP");
  await expect(page.locator(".source-detail")).toContainText("PDF p. 262 · Página impresa 248");
  await expect(page.locator(".source-detail")).toContainText(/Tema nominal|Alias nominal/);
  await expect(page.locator(".source-detail")).toContainText("Fuerte");
  await page.screenshot({ path: path.join(screenshots, "lm-xv-primary.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "named-topic-match.png"), fullPage: true });

  await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  const apostrophe = await ask(page, "Tisha B'Av");
  assertTishaPayload(apostrophe, "Tisha B'Av");
  await expect(page.locator(".user-turn h2").last()).toHaveText("Tisha B'Av");
  await expect(page.locator("body")).not.toContainText("Término individual");
  await expect(page.locator("body")).not.toContainText("Insuficiente");

  const works = await ask(page, "¿en qué obras aparece?");
  expect(works.named_topic.canonical_id).toBe("jewish_calendar.tisha_beav");
  await page.screenshot({ path: path.join(screenshots, "follow-up.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Fuentes", exact: true }).click();
  await expect(page.locator(".sources.open")).toContainText("PDF p. 262");
  await page.screenshot({ path: path.join(screenshots, "mobile.png"), fullPage: true });
  await page.keyboard.press("Escape");

  await page.setViewportSize({ width: 1280, height: 720 });
  await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  const hebrew = await ask(page, "תשעה באב");
  expect(hebrew.named_topic.canonical_id).toBe("jewish_calendar.tisha_beav");
  await expect(page.locator('.user-turn h2[dir="rtl"]').last()).toHaveText("תשעה באב");
  await page.screenshot({ path: path.join(screenshots, "hebrew-variant.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "rtl.png"), fullPage: true });

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter((item) => ["critical", "serious"].includes(item.impact ?? ""))).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
  await expect(page).toHaveURL(/\/login$/);
});

test("real deterministic fallback keeps the named topic and hides ValidationError", async ({ page }) => {
  test.setTimeout(120_000);
  fs.mkdirSync(screenshots, { recursive: true });
  await login(page);
  await page.route("**/library/investigative-qa/v1", async (route) => {
    const request = route.request();
    const body = request.postDataJSON();
    body.ai = { ...body.ai, enabled: false };
    const response = await route.fetch({ postData: JSON.stringify(body) });
    await route.fulfill({ response });
  });
  const payload = await ask(page, "tisha beav");
  assertTishaPayload(payload, "tisha beav");
  expect(payload.execution.fallback_used).toBe(true);
  await expect(page.locator("body")).not.toContainText("ValidationError");
  await page.locator("details").filter({ hasText: "Detalles de la consulta" }).locator("summary").click();
  await expect(page.getByText(/analizador determinístico/)).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, "fallback-result.png"), fullPage: true });
});

test("named-topic empty rendering omits empty evidence structures", async ({ page }) => {
  fs.mkdirSync(screenshots, { recursive: true });
  await login(page);
  await page.route("**/library/investigative-qa/v1", (route) => route.fulfill({ json: {
    status: "no_evidence", intent: "concept_lookup",
    query_understanding: { original_query: "Tishá BeAv", intent: "concept_lookup", operation: "find_named_topic", subject_type: "named_topic", subject_raw: "Tishá BeAv", subject_canonical: "Tishá BeAv", ai_used: false, ai_accepted: false, fallback_used: true, requires_clarification: false },
    named_topic: { canonical_id: "jewish_calendar.tisha_beav", canonical_label: "Tishá BeAv", topic_type: "jewish_calendar_observance", matched_alias: "Tishá BeAv", alias_match_kind: "exact_alias", match_language: "es", match_script: "Latin", variants_searched: ["Tishá BeAv", "Tisha B'Av", "9 de Av", "תשעה באב"] },
    answer_text: "", answer_markdown: "", summary: "Sin evidencia", conversation: { conversation_id: null, turn_id: null }, works_consulted: [], hits: [], claims: [], primary_evidence_ids: [], evidence_counts: { primary: 0, contextual: 0, additional_literal: 0 }, evidence_matrix: [], cross_corpus_matrix: [], warnings: [], not_found: ["Tishá BeAv"], execution: { fallback_used: true },
  }}));
  await ask(page, "Tishá BeAv");
  await expect(page.getByText(/No encontré referencias verificables a «Tishá BeAv»/)).toBeVisible();
  await expect(page.getByText("Matriz de evidencia", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Cruces entre obras", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/0 evidencias principales/)).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshots, "clean-empty-state.png"), fullPage: true });
});

test("baseline fixtures document the empty and truncated pre-fix states", async ({ page }) => {
  fs.mkdirSync(screenshots, { recursive: true });
  await login(page);
  const oldResponse = (subject: string | null) => ({
    status: "no_evidence", intent: subject ? "concept_lookup" : "unknown",
    interpretation: { language: "unknown", secondary_languages: [], intent: subject ? "concept_lookup" : "unknown", instruction_language: "unknown", instruction: null, query_subjects: subject ? [{ kind: "concept", raw: subject, normalized: subject.toLowerCase(), language: "es", script: "latin", variants: [{ value: subject.toLowerCase(), kind: "exact" }] }] : [], literal_phrases: [], relations: [], requested_works: [], confidence: subject ? 0.96 : 0.45, ai_used: false, fallback_used: true },
    answer_text: "No se encontró evidencia suficiente para establecer la relación solicitada.", answer_markdown: "No se encontró evidencia suficiente para establecer la relación solicitada.", summary: "Sin evidencia", conversation: { conversation_id: null, turn_id: null }, works_consulted: [], hits: [], claims: [], primary_evidence_ids: [], evidence_counts: { primary: 0, contextual: 0, additional_literal: 0 }, evidence_matrix: [], cross_corpus_matrix: [], warnings: ["ai_interpretation_fallback:ValidationError"], not_found: subject ? [subject] : [], execution: { fallback_used: true },
  });
  await page.route("**/library/investigative-qa/v1", (route) => route.fulfill({ json: oldResponse(null) }));
  await ask(page, "tisha beav");
  await page.screenshot({ path: path.join(screenshots, "before-tisha-beav-empty.png"), fullPage: true });
  await page.unroute("**/library/investigative-qa/v1");
  await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  await page.route("**/library/investigative-qa/v1", (route) => route.fulfill({ json: oldResponse("tisha") }));
  await ask(page, "Tisha B'Av");
  await expect(page.locator(".query-interpretation")).toContainText("Busqué el concepto: tisha");
  await page.screenshot({ path: path.join(screenshots, "before-tisha-bav-truncated.png"), fullPage: true });
});

test("real UI named-topic resolution is stable twenty of twenty for both focal queries", async ({ page }) => {
  test.setTimeout(600_000);
  fs.mkdirSync(reportRoot, { recursive: true });
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await login(page);
  await page.route("**/library/investigative-qa/v1", async (route) => {
    const request = route.request();
    const body = request.postDataJSON();
    body.ai = { ...body.ai, enabled: false };
    const response = await route.fetch({ postData: JSON.stringify(body) });
    await route.fulfill({ response });
  });
  const results: Array<Record<string, unknown>> = [];
  for (const query of ["tisha beav", "Tisha B'Av"]) {
    for (let iteration = 1; iteration <= 20; iteration += 1) {
      if (results.length) await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
      const started = Date.now();
      const payload = await ask(page, query);
      const primary = assertTishaPayload(payload, query);
      await expect(page.locator(".query-interpretation").last()).toContainText("Tishá BeAv");
      await expect(page.locator("body")).not.toContainText("Busqué el concepto: tisha");
      results.push({ query, iteration, duration_ms: Date.now() - started, canonical_id: payload.named_topic.canonical_id, subject_raw: payload.query_understanding.subject_raw, evidence_id: primary.hit_id, pdf_page: primary.pdf_page, match_kind: primary.literal_match_kind, pass: true });
    }
  }
  fs.writeFileSync(path.join(reportRoot, "repeat_20x_ui_runtime.json"), `${JSON.stringify({ total: 40, passed: 40, failed: 0, console_errors: consoleErrors, page_errors: pageErrors, results }, null, 2)}\n`);
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});
