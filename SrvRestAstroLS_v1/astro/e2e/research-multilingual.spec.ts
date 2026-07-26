import fs from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { fulfillConfirmationPhases } from "./research-confirmation-helpers";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
const screenshots = path.resolve(import.meta.dirname, "../../../data/reports/breslov/2026-07-16-research-workspace-v1/screenshots");
fs.mkdirSync(screenshots, { recursive: true });

async function login(page: Page) {
  await page.goto("/login");
  await expect(page.locator("astro-island:not([ssr])")).toBeAttached();
  await page.fill("#login-email", email!); await page.fill("#login-password", password!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible();
}

async function ask(page: Page, question: string) {
  const pending = page.waitForResponse(response => response.url().endsWith("/library/investigative-qa/v1") && response.request().method() === "POST" && response.request().postDataJSON()?.phase === "analyze");
  await page.getByTestId("research-question").fill(question); await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click();
  const response = await pending; expect(response.status()).toBe(200);
  return response.json();
}

test.skip(!email || !password, "requires configured E2E administrator credentials");

test("natural Hebrew concept query, scoped follow-up and source request remain grounded", async ({ page }) => {
  test.setTimeout(240_000); const consoleErrors: string[] = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.setViewportSize({ width: 1366, height: 768 }); await login(page);

  const question = "אתה מחפש איפה נמצא מושג העקרב.";
  const main = await ask(page, question);
  expect(main.status).toBe("ok"); expect(main.intent).toBe("concept_lookup");
  expect(main.interpretation.language).toBe("he");
  expect(main.interpretation.query_subjects[0]).toMatchObject({ raw: "העקרב", normalized: "עקרב", language: "he" });
  expect(main.search_plan.queries).not.toContain(question);
  expect(main.search_plan.queries).toEqual(expect.arrayContaining(["העקרב", "עקרב"]));
  expect(main.primary_evidence_ids.length).toBeGreaterThan(0);
  await expect(page.locator(".user-turn h2").last()).toHaveText(question);
  await expect(page.getByTestId("interpretation-card").last()).toContainText("עקרב");
  await page.screenshot({ path: path.join(screenshots, "hebrew-concept-after.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "scorpion-language-priority.png"), fullPage: true });

  const primary = main.hits.find((hit: any) => main.primary_evidence_ids.includes(hit.hit_id));
  await page.getByRole("button", { name: /Ver fuente de:/ }).first().click();
  await expect(page.locator(".source-detail")).toHaveAttribute("data-evidence-id", primary.hit_id);
  await expect(page.locator(".source-detail .evidence-meta")).toHaveAttribute("dir", "ltr");
  await page.screenshot({ path: path.join(screenshots, "hebrew-concept-source.png"), fullPage: true });

  const followup = await ask(page, "ומה בליקוטי הלכות");
  expect(followup.intent).toBe("follow_up"); expect(followup.works_consulted).toEqual(["lh"]);
  expect(followup.interpretation.query_subjects[0].normalized).toBe("עקרב");
  await page.screenshot({ path: path.join(screenshots, "hebrew-follow-up.png"), fullPage: true });

  const source = await ask(page, "תראה לי את המקור העיקרי");
  expect(source.intent).toBe("source_request"); expect(source.interpretation.query_subjects[0].normalized).toBe("עקרב");
  expect(source.primary_evidence_ids.length).toBeGreaterThan(0);

  await page.setViewportSize({ width: 820, height: 1180 });
  await page.getByRole("button", { name: "Fuentes", exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "hebrew-mobile.png"), fullPage: true });
  await page.setViewportSize({ width: 320, height: 568 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter(item => item.impact === "critical")).toEqual([]);
  expect(consoleErrors).toEqual([]);

  await page.setViewportSize({ width: 1366, height: 768 }); await page.locator(".desktop-action").filter({ hasText: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("mixed queries and Hebrew intent matrix stay distinct from PDF copy-paste", async ({ page }) => {
  test.setTimeout(360_000); await page.setViewportSize({ width: 1536, height: 1024 }); await login(page);
  const mixed = [
    ["dónde aparece עקרב", "mixed-es-he.png"],
    ["where is עקרב mentioned", "mixed-en-he.png"],
    ["איפה מופיע el concepto עקרב", "mixed-he-es.png"],
  ] as const;
  for (const [query, screenshot] of mixed) {
    const payload = await ask(page, query);
    expect(payload.intent).toBe("concept_lookup"); expect(payload.interpretation.query_subjects[0].normalized).toBe("עקרב");
    await page.screenshot({ path: path.join(screenshots, screenshot), fullPage: true });
    await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  }

  const intents = [
    ["איפה נמצא המושג עקרב", "concept_lookup"],
    ["איפה מופיע תהלתי אחטם לך", "literal_lookup"],
    ["מה הקשר בין דם לדיבור", "relation_query"],
    ["מה פירוש תהלתי אחטם לך", "translation_or_explanation"],
  ] as const;
  for (const [query, intent] of intents) {
    const payload = await ask(page, query); expect(payload.intent, query).toBe(intent);
    await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  }
  await page.screenshot({ path: path.join(screenshots, "literal-vs-concept.png"), fullPage: true });

  const copied = await ask(page, "ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך donde esta");
  expect(copied.status).toBe("ok"); expect(copied.intent).toBe("literal_lookup");
  expect(copied.interpretation.literal_search_normalized).toBe("תהלתי אחטם לך");
  expect(copied.hits.find((hit: any) => copied.primary_evidence_ids.includes(hit.hit_id))).toMatchObject({ pdf_page: 96, printed_page: 76 });
});

test("controlled diagnostics document the blocked state and discreet AI fallback", async ({ page }) => {
  test.setTimeout(120_000); await page.setViewportSize({ width: 1366, height: 768 }); await login(page);
  const endpoint = "**/library/investigative-qa/v1";
  const response = (fallback: boolean) => ({
    status: "no_evidence", intent: fallback ? "concept_lookup" : "literal_lookup",
    interpretation: { language: "he", secondary_languages: [], intent: fallback ? "concept_lookup" : "literal_lookup", instruction_language: "he", instruction: "איפה נמצא", query_subjects: fallback ? [{ kind: "concept", raw: "העקרב", normalized: "עקרב", language: "he", script: "hebrew", variants: [{ value: "העקרב", kind: "exact" }, { value: "עקרב", kind: "definite_article_removed" }] }] : [], literal_phrases: [], relations: [], requested_works: [], confidence: fallback ? 0.95 : 0.3, ai_used: false, fallback_used: fallback },
    answer_text: "No se encontró evidencia suficiente en el corpus consultado.", answer_markdown: "No se encontró evidencia suficiente en el corpus consultado.", summary: "Sin evidencia", conversation: { conversation_id: null, turn_id: null }, works_consulted: [], hits: [], claims: [], primary_evidence_ids: [], evidence_counts: { primary: 0, contextual: 0, additional_literal: 0 }, evidence_matrix: [], cross_corpus_matrix: [], warnings: fallback ? ["La interpretación IA no estuvo disponible; se aplicó el analizador determinístico."] : [], not_found: [], execution: { ai_used: false, fallback_used: fallback },
  });
  await page.route(endpoint, route => fulfillConfirmationPhases(route, response(false)));
  await ask(page, "אתה מחפש איפה נמצא מושג העקרב.");
  await page.screenshot({ path: path.join(screenshots, "hebrew-concept-before.png"), fullPage: true });
  await page.unroute(endpoint); await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  await page.route(endpoint, route => fulfillConfirmationPhases(route, response(true)));
  await ask(page, "אתה מחפש איפה נמצא מושג העקרב.");
  await expect(page.getByTestId("interpretation-card")).toContainText("העקרב");
  await expect(page.getByText(/analizador determinístico/)).toBeHidden();
  await page.locator("details").filter({ hasText: "Detalles de la consulta" }).locator("summary").click();
  await expect(page.getByText(/analizador determinístico/)).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, "ai-fallback.png"), fullPage: true });
});
