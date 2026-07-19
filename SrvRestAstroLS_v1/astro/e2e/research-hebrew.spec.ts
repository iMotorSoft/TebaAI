import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

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

async function selectEvidence(page: Page, hitId: string) {
  const choice = page.locator(`.source-list button[data-evidence-id="${hitId}"]`).first();
  const owner = choice.locator("xpath=ancestor::details[1]");
  if (await owner.count()) await owner.locator("summary").click();
  await choice.click();
}

async function assertHebrewBlock(page: Page, hitId: string, expected: string) {
  const block = page.locator(`.source-detail[data-evidence-id="${hitId}"] blockquote`);
  await expect(block).toHaveAttribute("lang", "he"); await expect(block).toHaveAttribute("dir", "rtl");
  await expect(block).toHaveText(expected);
  const styles = await block.evaluate((element) => { const style = getComputedStyle(element); return { direction: style.direction, unicodeBidi: style.unicodeBidi, textAlign: style.textAlign, letterSpacing: style.letterSpacing, wordSpacing: style.wordSpacing, wordBreak: style.wordBreak, fontSize: style.fontSize, fontStyle: style.fontStyle, lineHeight: style.lineHeight, fontFamily: style.fontFamily, overflow: element.scrollWidth > element.clientWidth + 1 }; });
  expect(styles.direction).toBe("rtl"); expect(styles.unicodeBidi).toBe("plaintext"); expect(styles.textAlign).toBe("right");
  expect(styles.letterSpacing).toBe("normal"); expect(["normal", "0px"]).toContain(styles.wordSpacing); expect(styles.wordBreak).not.toBe("break-all");
  expect(Number.parseFloat(styles.fontSize)).toBeGreaterThanOrEqual(17); expect(Number.parseFloat(styles.lineHeight)).toBeGreaterThanOrEqual(28);
  expect(styles.fontStyle).toBe("normal"); expect(styles.fontFamily).toMatch(/Noto (Serif|Sans) Hebrew/); expect(styles.overflow).toBe(false);
  expect(expected).not.toMatch(/[\u0590-\u05ff]\s[\u0591-\u05c7]/u);
}

test.skip(!email || !password, "requires configured E2E administrator credentials");
test("real scorpion evidence preserves logical Hebrew on desktop, tablet and mobile", async ({ page }) => {
  test.setTimeout(180_000); const critical: string[] = [];
  page.on("console", message => { if (message.type() === "error") critical.push(message.text()); });
  await page.setViewportSize({ width: 1366, height: 768 }); await login(page);
  const responsePromise = page.waitForResponse(response => response.url().endsWith("/library/investigative-qa/v1") && response.request().method() === "POST");
  await page.getByTestId("research-question").fill("donde aparece el termino escorpion"); await page.getByTestId("research-submit").click();
  const response = await responsePromise; expect(response.status()).toBe(200); const payload = await response.json();
  const hit = payload.hits.find((item: any) => item.work_code === "lmii" && item.pdf_page === 28 && item.display_normalization === "pdf_glyph_geometry_nfc_v1");
  expect(hit, "real LMII Hebrew scorpion evidence").toBeTruthy(); expect(hit.quote).toMatch(/[\u0590-\u05ff]\s[\u0591-\u05c7]/u);
  expect(hit.display_snippet).toContain("עַקְרַבֵּי"); expect(hit.display_snippet.normalize("NFC")).toBe(hit.display_snippet);
  await selectEvidence(page, hit.hit_id); await assertHebrewBlock(page, hit.hit_id, hit.display_snippet);
  await expect(page.locator(".source-detail .evidence-meta")).toHaveAttribute("dir", "ltr");
  await page.screenshot({ path: path.join(screenshots, "hebrew-card-desktop.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-page-numbers.png"), fullPage: true });

  await page.setViewportSize({ width: 820, height: 1180 }); const tabletSources = page.getByRole("button", { name: "Fuentes", exact: true }); await tabletSources.click();
  await assertHebrewBlock(page, hit.hit_id, hit.display_snippet); await expect(page.locator(".sources.open")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "hebrew-tablet-drawer.png"), fullPage: true });
  await page.keyboard.press("Escape"); await expect(page.locator(".sources.open")).toHaveCount(0); await expect(tabletSources).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 }); await page.getByRole("button", { name: "Fuentes", exact: true }).click();
  await assertHebrewBlock(page, hit.hit_id, hit.display_snippet); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "hebrew-mobile-drawer.png"), fullPage: true });
  await page.keyboard.press("Escape"); await page.setViewportSize({ width: 320, height: 568 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  expect(critical).toEqual([]);
});

test("Hebrew composer and rendered question retain direction", async ({ page }) => {
  test.setTimeout(120_000); await page.setViewportSize({ width: 390, height: 844 }); await login(page);
  const composer = page.getByTestId("research-question"); await composer.fill("מה נאמר על תפילה 2:7?");
  await expect(composer).toHaveAttribute("dir", "rtl"); await expect(composer).toHaveAttribute("lang", "he");
  await page.screenshot({ path: path.join(screenshots, "hebrew-composer.png"), fullPage: true });
  const responsePromise = page.waitForResponse(response => response.url().endsWith("/library/investigative-qa/v1") && response.request().method() === "POST");
  await composer.press("Enter"); await responsePromise;
  const question = page.locator(".user-turn h2").last(); await expect(question).toHaveText("מה נאמר על תפילה 2:7?"); await expect(question).toHaveAttribute("dir", "rtl"); await expect(question).toHaveAttribute("lang", "he");
  await expect(composer).toHaveAttribute("dir", "ltr");
});

test("real Hebrew literal lookup traces niqqud variants to physical page 96", async ({ page }) => {
  test.setTimeout(180_000); const consoleErrors: string[] = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.setViewportSize({ width: 1366, height: 768 }); await login(page);

  async function ask(question: string) {
    const responsePromise = page.waitForResponse(response => response.url().endsWith("/library/investigative-qa/v1") && response.request().method() === "POST");
    await page.getByTestId("research-question").fill(question); await page.getByTestId("research-submit").click();
    const response = await responsePromise; expect(response.status()).toBe(200); const payload = await response.json();
    expect(payload.status).toBe("ok"); expect(payload.intent).toBe("literal_lookup");
    const hit = payload.hits.find((item: any) => payload.primary_evidence_ids.includes(item.hit_id));
    expect(hit).toMatchObject({ work_code: "lmi", pdf_page: 96, printed_page: 76, section: "LIKUTEY MOHARÁN #2:7", physical_file_name: "LIKUTEY MOHARÁN I int (imprenta).pdf" });
    expect(hit.quote).toContain("תְּהִלָּתִי אֶחְטָם לָךְ"); expect(hit.source_sha256).toBe("71fb3c763c34d13465441c57b2bf3a65629fcdc37a7588f21e4fbf21f984b8d7");
    expect(payload.answer_markdown).not.toContain("relación solicitada");
    await expect(page.locator(".no-evidence")).toHaveCount(0); await expect(page.locator(".source-detail .evidence-meta").first()).toContainText("PDF p. 96 · Página impresa 76 · LIKUTEY MOHARÁN #2:7");
    await expect(page.locator(".source-detail .evidence-meta").nth(1)).toContainText("LIKUTEY MOHARÁN I int (imprenta).pdf");
    await assertHebrewBlock(page, hit.hit_id, hit.snippet);
    return { hit, payload };
  }

  const copiedQuestion = "ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך donde esta";
  const copied = await ask(copiedQuestion);
  expect(copied.payload.interpretation).toMatchObject({
    literal_raw: "ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך",
    instruction: "donde esta",
    literal_search_normalized: "תהלתי אחטם לך",
    selected_candidate: "תהלתי אחטם לך",
  });
  expect(copied.payload.search_plan.queries).toEqual(["תהלתי אחטם לך"]);
  await expect(page.locator(".user-turn h2").last()).toHaveText(copiedQuestion);
  await page.screenshot({ path: path.join(screenshots, "hebrew-copypaste-after.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-copypaste-source.png"), fullPage: true });
  await page.setViewportSize({ width: 1536, height: 1024 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "hebrew-copypaste-1536.png"), fullPage: true });
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.getByRole("button", { name: "Fuentes", exact: true }).click();
  await assertHebrewBlock(page, copied.hit.hit_id, copied.hit.snippet);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "hebrew-copypaste-tablet.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Fuentes", exact: true }).click();
  await assertHebrewBlock(page, copied.hit.hit_id, copied.hit.snippet);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "hebrew-copypaste-mobile.png"), fullPage: true });
  await page.keyboard.press("Escape"); await page.setViewportSize({ width: 1366, height: 768 });
  await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();

  const pointed = await ask("תְּהִלָּתִי אֶחְטָם לָךְ");
  await page.screenshot({ path: path.join(screenshots, "hebrew-with-niqqud.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-literal-after.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-printed-page-76.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-source-panel.png"), fullPage: true });
  await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  const unpointed = await ask("תהלתי אחטם לך");
  expect(unpointed.hit.hit_id).toBe(pointed.hit.hit_id); expect(unpointed.hit.document_id).toBe(pointed.hit.document_id); expect(unpointed.hit.page_anchor_id).toBe(pointed.hit.page_anchor_id);
  expect(copied.hit.hit_id).toBe(pointed.hit.hit_id); expect(copied.hit.page_anchor_id).toBe(pointed.hit.page_anchor_id);
  await page.screenshot({ path: path.join(screenshots, "hebrew-copypaste-clean-equivalence.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-without-niqqud.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 }); await page.getByRole("button", { name: "Fuentes", exact: true }).click();
  await assertHebrewBlock(page, unpointed.hit.hit_id, unpointed.hit.snippet); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshots, "hebrew-literal-mobile.png"), fullPage: true }); await page.screenshot({ path: path.join(screenshots, "hebrew-mobile.png"), fullPage: true }); await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 320, height: 568 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  const accessibility = await new AxeBuilder({ page }).analyze(); expect(accessibility.violations.filter(item => item.impact === "critical")).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("captures controlled pre-index baseline and real negative literal result", async ({ page }) => {
  test.setTimeout(120_000); await page.setViewportSize({ width: 1366, height: 768 }); await login(page);
  await page.getByRole("button", { name: "Filtros" }).last().click();
  const filters = page.getByRole("dialog", { name: "Filtros de investigación" });
  await filters.getByLabel("Likutey Moharán I — edición española BRI").uncheck(); await filters.getByLabel("Likutey Moharán XV").uncheck(); await filters.getByRole("button", { name: "Aplicar filtros" }).click();
  await page.getByTestId("research-question").fill("ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך donde esta"); await page.getByTestId("research-submit").click();
  await expect(page.locator(".no-evidence")).toBeVisible({ timeout: 30_000 }); await page.screenshot({ path: path.join(screenshots, "hebrew-literal-before.png"), fullPage: true }); await page.screenshot({ path: path.join(screenshots, "hebrew-copypaste-before.png"), fullPage: true });
  await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click(); await page.getByRole("button", { name: "Filtros" }).last().click();
  await page.getByRole("dialog", { name: "Filtros de investigación" }).getByLabel("Likutey Moharán I — edición española BRI").check();
  await page.getByRole("dialog", { name: "Filtros de investigación" }).getByLabel("Likutey Moharán XV").check();
  await page.getByRole("dialog", { name: "Filtros de investigación" }).getByRole("button", { name: "Aplicar filtros" }).click();
  await page.getByTestId("research-question").fill("תהלתי אחטמ לך"); await page.getByTestId("research-submit").click();
  await expect(page.locator(".no-evidence")).toBeVisible({ timeout: 30_000 }); await page.screenshot({ path: path.join(screenshots, "hebrew-no-evidence-negative.png"), fullPage: true }); await page.screenshot({ path: path.join(screenshots, "hebrew-copypaste-negative.png"), fullPage: true });
});

test("real Hebrew corpus batch renders ten of ten in logical RTL", async ({ page }) => {
  test.setTimeout(360_000); await page.setViewportSize({ width: 1536, height: 1024 }); await login(page);
  const cases = ["escorpión", "plegaria", "temor", "tristeza", "Rabí Natán", "Zohar", "alma", "habla", "pureza", "hitbodedut"];
  for (const [index, query] of cases.entries()) {
    const responsePromise = page.waitForResponse(response => response.url().endsWith("/library/investigative-qa/v1") && response.request().method() === "POST");
    await page.getByTestId("research-question").fill(query); await page.getByTestId("research-submit").click();
    const response = await responsePromise; expect(response.status(), query).toBe(200); const payload = await response.json();
    const normalized = payload.hits.filter((item: any) => item.display_normalization === "pdf_glyph_geometry_nfc_v1" && /[\u0590-\u05ff]/u.test(item.display_snippet ?? ""));
    expect(normalized.length, `${query}: readable Hebrew evidence`).toBeGreaterThan(0);
    const hit = normalized.sort((a: any, b: any) => (b.display_snippet?.match(/[\u0590-\u05ff]/gu)?.length ?? 0) - (a.display_snippet?.match(/[\u0590-\u05ff]/gu)?.length ?? 0))[0];
    await selectEvidence(page, hit.hit_id); await assertHebrewBlock(page, hit.hit_id, hit.display_snippet);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), query).toBe(true);
    await page.screenshot({ path: path.join(screenshots, `hebrew-batch-${String(index + 1).padStart(2, "0")}.png`), fullPage: true });
    await page.locator(".desktop-action").filter({ hasText: "Nueva investigación" }).click();
  }
});

test("mixed Markdown isolates Hebrew, Spanish metadata and references", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const hebrew = "אָמַר רַבָּה: בְּרֵאשִׁית 2:7 · Bava Batra 74a · Likutey Moharán II · § 19 — זהו טקסט עברי ארוך עם נִקּוּד, סוֹגְרַיִם (כָּאֵלֶּה) וְצִיטּוּט \"שָׁלוֹם\".";
  await page.route("**/library/investigative-qa/v1", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
    status: "ok", answer_text: "Respuesta", answer_markdown: `## Respuesta\n\nTexto español seguido de עברית and English 2:7.\n\n> ${hebrew}\n\n| Obra | Cita |\n|---|---|\n| LM II | ${hebrew} |`, summary: "Síntesis española con fuente hebrea.", conversation: { conversation_id: null, turn_id: null }, works_consulted: ["lmii"],
    hits: [{ hit_id: "mixed-hebrew", work_code: "lmii", work_title: "Likutey Moharán II", pdf_page: 210, printed_page: 200, quote: hebrew, snippet: hebrew, display_quote: hebrew, display_snippet: hebrew, display_normalization: "fixture_nfc", evidence_type: "literal_same_page", literal_strength: "strong", evidence_strength: "strong", relation_relevance: "direct_relation", matched_terms: ["עברית"], matched_concepts: ["עברית"], is_primary: true, source_layer: "page_literal", warnings: [] }],
    claims: [{ claim_id: "mixed-claim", text: "La evidencia contiene una cita hebrea vinculada.", strength: "strong", evidence_ids: ["mixed-hebrew"], primary_evidence_id: "mixed-hebrew" }], primary_evidence_ids: ["mixed-hebrew"], evidence_counts: { primary: 1, contextual: 0, additional_literal: 0 }, evidence_matrix: [{ work_code: "lmii", hits: 1, primary_hits: 1 }], cross_corpus_matrix: [], warnings: [], not_found: [], execution: {},
  }) }));
  await page.setViewportSize({ width: 1536, height: 1024 }); await login(page); await page.getByTestId("research-question").fill("texto mixto"); await page.getByTestId("research-submit").click();
  await expect(page.locator(".enriched-markdown blockquote.research-hebrew-text")).toHaveAttribute("lang", "he");
  await expect(page.locator(".enriched-markdown blockquote.research-hebrew-text")).toHaveAttribute("dir", "rtl");
  await expect(page.locator(".enriched-markdown .research-mixed-text bdi").first()).toHaveAttribute("lang", "he");
  await expect(page.locator(".source-detail .evidence-meta")).toContainText("PDF p. 210 · Página impresa 200");
  await expect(page.locator(".source-detail .evidence-meta")).toHaveAttribute("dir", "ltr");
  await assertHebrewBlock(page, "mixed-hebrew", hebrew);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter(item => item.impact === "critical")).toEqual([]);
  await page.evaluate(() => { document.body.style.zoom = "2"; }); await expect(page.locator(".source-detail blockquote")).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, "hebrew-mixed-text.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-long-evidence.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshots, "hebrew-source-panel.png"), fullPage: true });
});
