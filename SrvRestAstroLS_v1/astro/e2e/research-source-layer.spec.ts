import fs from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

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

function assertGolden(payload: any, instructionLanguage: "es" | "en" | "he") {
  expect(payload.status).toBe("ok");
  expect(payload.intent).toBe("literal_lookup");
  expect(payload.interpretation.instruction_language).toBe(instructionLanguage);
  expect(payload.interpretation.primary_retrieval_language).toBe("he");
  const primary = payload.hits.find((hit: any) => payload.primary_evidence_ids.includes(hit.hit_id));
  expect(primary).toMatchObject({
    physical_file_name: "LIKUTEY MOHARÁN XV KDP.pdf", physical_pdf_page: 229,
    printed_page: 215, section: "LIKUTEY MOHARÁN II #83:8", language: "he",
    direction: "rtl", source_layer: "biblical_quote_in_lesson",
    source_layer_confidence: "high", is_original_language: true,
    is_primary_language_match: true, is_translation: false,
  });
  expect(primary.match_text).toBe("וְהָיָה עֵינַי וְלִבִּי שָׁם");
  expect(primary.paragraph_text).toContain("וְאוֹר הָעֵינִין");
  expect(primary.parallel_texts[0]).toMatchObject({ language: "es", source_layer: "editorial_translation", link_type: "parallel_translation", physical_pdf_page: 228, printed_page: 214 });
  expect(payload.hits[0].hit_id).toBe(primary.hit_id);
  expect(payload.answer_markdown).not.toContain("Sin evidencia suficiente");
  return primary;
}

test.skip(!email || !password, "requires configured E2E administrator credentials");

test("real LM XV source-language priority and editorial layer remain auditable", async ({ page }) => {
  test.setTimeout(300_000); const errors: string[] = [];
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.setViewportSize({ width: 1536, height: 1024 }); await login(page);

  const spanish = await ask(page, "¿Dónde aparece וְהָיוּ עֵינַי וְלִבִּי שָׁם?");
  const primary = assertGolden(spanish, "es");
  const source = page.locator(`.source-detail[data-evidence-id="${primary.hit_id}"]`);
  await expect(source.getByRole("heading", { name: "Texto original en hebreo" })).toBeVisible();
  const original = source.locator("blockquote").first();
  await expect(original).toHaveAttribute("lang", "he"); await expect(original).toHaveAttribute("dir", "rtl");
  await expect(original).toContainText("וְהָיָה עֵינַי וְלִבִּי שָׁם");
  await expect(source).toContainText("Cita bíblica dentro de la lección");
  await expect(source.getByRole("heading", { name: "Traducción / ampliación" })).toBeVisible();
  expect(await source.locator("blockquote").allTextContents()).toEqual(expect.arrayContaining([expect.stringContaining("Mis ojos y Mi corazón") ]));
  await page.screenshot({ path: path.join(screenshots, "lm-xv-page-215-source.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-primary-evidence.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-paragraph.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "source-layer-biblical-quote.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "spanish-translation-secondary.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "mixed-spanish-hebrew.png"), fullPage: true });

  for (const [query, language, shot] of [
    ["איפה מופיע הפסוק והיו עיני ולבי שם", "he", "hebrew-query.png"],
    ["where does וְהָיוּ עֵינַי וְלִבִּי שָׁם appear", "en", "mixed-english-hebrew.png"],
  ] as const) {
    await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
    const payload = await ask(page, query); assertGolden(payload, language);
    await page.screenshot({ path: path.join(screenshots, shot), fullPage: true });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Fuentes", exact: true }).click();
  await expect(page.locator(".sources.open blockquote[lang=he][dir=rtl]").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "mobile-hebrew-source.png"), fullPage: true });
  await page.keyboard.press("Escape");
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter(item => item.impact === "critical")).toEqual([]);
  expect(errors).toEqual([]);
});

test("real source-layer follow-ups preserve the same evidence identity", async ({ page }) => {
  test.setTimeout(300_000); await page.setViewportSize({ width: 1366, height: 768 }); await login(page);
  const first = await ask(page, "איפה מופיע הפסוק והיו עיני ולבי שם");
  const primary = assertGolden(first, "he");
  const layerQuestion = "¿Es parte de la lección del Rebe, una cita o una nota?";
  const layer = await ask(page, layerQuestion);
  const expected = "Sí. Es una cita bíblica incluida dentro de la lección del Rebe. No es una nota editorial.";
  expect(layer.status).toBe("ok");
  expect(layer.claims[0]).toMatchObject({ text: expected, strength: "strong", primary_evidence_id: primary.evidence_id });
  expect(layer.answer_markdown).toContain(`- ${expected}`);
  expect(layer.answer_markdown).not.toContain("dependencia doctrinal");
  expect(layer.answer_markdown).not.toContain("`direct_relation`");
  expect(layer.hits.find((hit: any) => layer.primary_evidence_ids.includes(hit.hit_id))?.evidence_id).toBe(primary.evidence_id);
  await expect(page.locator(".claim-list li").first()).toContainText(expected);
  for (const question of [
    "Mostrame el párrafo completo en hebreo.",
    "¿Existe traducción al español?",
    "¿En qué página física está?",
  ]) {
    const payload = await ask(page, question);
    expect(payload.status, question).toBe("ok");
    expect(payload.hits.find((hit: any) => payload.primary_evidence_ids.includes(hit.hit_id))?.evidence_id, question).toBe(primary.evidence_id);
  }
});
