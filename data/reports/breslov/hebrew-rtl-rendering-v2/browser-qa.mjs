import fs from "node:fs";
import path from "node:path";
import { chromium } from "../../../../SrvRestAstroLS_v1/astro/node_modules/@playwright/test/index.mjs";

const dir = path.dirname(new URL(import.meta.url).pathname);
const BASE = "http://127.0.0.1:3008";
const out = { url: BASE, console_errors: [], http_errors: [], cases: [] };
const write = (name, data) => fs.writeFileSync(path.join(dir, name), JSON.stringify(data, null, 2) + "\n");
const normalize = text => text.replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/gu, "").normalize("NFC");

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await context.newPage();
page.on("console", m => { if (m.type() === "error") out.console_errors.push(m.text()); });
page.on("response", r => { if (r.status() >= 500) out.http_errors.push({ url: r.url(), status: r.status() }); });

async function login() {
  await page.goto(`${BASE}/login`);
  await page.locator("#login-email").fill(process.env.TEBAAI_E2E_ADMIN_EMAIL);
  await page.locator("#login-password").fill(process.env.TEBAAI_E2E_ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await page.getByTestId("research-question").waitFor({ timeout: 60000 });
}

async function ask(question) {
  const pending = page.waitForResponse(
    r => r.url().includes("/library/investigative-qa/v1") && r.request().method() === "POST" && !r.request().postDataJSON()?.phase,
    { timeout: 300000 },
  );
  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click();
  const response = await pending;
  return { status: response.status(), body: await response.json() };
}

async function selectEvidence(hitId) {
  const detail = page.locator(`.source-detail[data-evidence-id="${hitId}"]`);
  if (await detail.count() && await detail.isVisible()) return detail;
  const button = page.locator(`.source-list button[data-evidence-id="${hitId}"]`).first();
  await button.evaluate(el => { const owner = el.closest("details"); if (owner) owner.open = true; });
  await button.scrollIntoViewIfNeeded();
  await button.click();
  await detail.waitFor({ timeout: 15000 });
  return detail;
}

async function blockquoteFacts(hitId) {
  return page.evaluate(id => {
    const detail = document.querySelector(`.source-detail[data-evidence-id="${id}"]`);
    const block = detail?.querySelector("blockquote");
    if (!block) return null;
    const style = getComputedStyle(block);
    const bdis = [...block.querySelectorAll("bdi")];
    return {
      hit_id: id,
      text: block.textContent,
      dir_attr: block.getAttribute("dir"),
      lang_attr: block.getAttribute("lang"),
      computed_direction: style.direction,
      computed_unicode_bidi: style.unicodeBidi,
      classes: block.className,
      has_presentation_forms: /[\ufb1d-\ufb4f]/u.test(block.textContent),
      presentation_codepoints: [...new Set(block.textContent.match(/[\ufb1d-\ufb4f]/gu) ?? [])].map(c => "U+" + c.codePointAt(0).toString(16).toUpperCase()),
      replacement_chars: (block.textContent.match(/\ufffd/gu) ?? []).length,
      bdi_count: bdis.length,
      bdis: bdis.map(b => ({
        dir: b.getAttribute("dir"),
        lang: b.getAttribute("lang"),
        text: b.textContent,
        computed_direction: getComputedStyle(b).direction,
        computed_white_space: getComputedStyle(b).whiteSpace,
        leading_or_trailing_space: /^\s|\s$/u.test(b.textContent),
        edge_punctuation: /^[.,;:()\[\]]|[.,;:()\[\]]$/u.test(b.textContent),
      })),
      block_overflow: block.scrollWidth > block.clientWidth + 1,
      document_overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      viewport: { width: window.innerWidth, height: window.innerHeight },
    };
  }, hitId);
}

async function equationFacts(hitId) {
  return page.evaluate(id => {
    const detail = document.querySelector(`.source-detail[data-evidence-id="${id}"]`);
    const block = detail?.querySelector("blockquote");
    const cells = [...(block?.querySelectorAll('bdi[dir="ltr"]') ?? [])].filter(b => /^[0-9]+\s*=/u.test(b.textContent));
    const charRect = (node, index) => {
      const range = document.createRange();
      range.setStart(node, index);
      range.setEnd(node, index + 1);
      const rect = range.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, right: rect.right };
    };
    return {
      hit_id: id,
      block_text: block?.textContent ?? "",
      cell_count: cells.length,
      document_overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      cells: cells.map(b => {
        const text = b.textContent;
        const node = b.firstChild;
        const eqIndex = text.indexOf("=");
        const hebrewIndex = text.search(/[\u05d0-\u05ea]/u);
        const number = node ? charRect(node, 0) : null;
        const equals = node ? charRect(node, eqIndex) : null;
        const hebrew = node ? charRect(node, hebrewIndex) : null;
        const box = b.getBoundingClientRect();
        return {
          text,
          dir: b.getAttribute("dir"),
          computed_white_space: getComputedStyle(b).whiteSpace,
          box: { x: box.x, y: box.y, width: box.width, height: box.height, right: box.right },
          number, equals, hebrew,
          number_left_of_equals: number.x < equals.x,
          equals_left_of_hebrew: equals.x < hebrew.x,
          same_visual_line: Math.abs(number.y - equals.y) < 2 && Math.abs(equals.y - hebrew.y) < 2,
          inside_viewport: box.x >= -1 && box.right <= window.innerWidth + 1,
          overflows_cell: b.scrollWidth > b.clientWidth + 1,
        };
      }),
    };
  }, hitId);
}

async function answerFacts() {
  return page.evaluate(() => {
    const roots = [...document.querySelectorAll(".enriched-markdown")];
    const root = roots[roots.length - 1];
    if (!root) return null;
    const bdis = [...root.querySelectorAll("bdi")];
    const punctuation = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!/[.,;:()\[\]«»“”]/u.test(node.data)) continue;
      punctuation.push({
        sample: node.data.match(/[.,;:()\[\]«»“”]/gu)?.slice(0, 5) ?? [],
        inside_bdi: Boolean(node.parentElement?.closest("bdi")),
      });
    }
    const paragraph = root.querySelector("p");
    return {
      markdown_text: root.textContent,
      paragraph_dir: paragraph?.getAttribute("dir") ?? null,
      paragraph_lang: paragraph?.getAttribute("lang") ?? null,
      paragraph_computed_direction: paragraph ? getComputedStyle(paragraph).direction : null,
      has_presentation_forms: /[\ufb1d-\ufb4f]/u.test(root.textContent),
      presentation_codepoints: [...new Set(root.textContent.match(/[\ufb1d-\ufb4f]/gu) ?? [])].map(c => "U+" + c.codePointAt(0).toString(16).toUpperCase()),
      has_latin: /[A-Za-zÀ-ÖØ-öø-ÿ]/u.test(root.textContent),
      bdi_count: bdis.length,
      bdis: bdis.map(b => ({
        dir: b.getAttribute("dir"),
        lang: b.getAttribute("lang"),
        text: b.textContent,
        computed_direction: getComputedStyle(b).direction,
        edge_punctuation: /^[.,;:()\[\]«»“”]|[.,;:()\[\]«»“”]$/u.test(b.textContent),
        leading_or_trailing_space: /^\s|\s$/u.test(b.textContent),
        only_hebrew: !/[A-Za-zÀ-ÖØ-öø-ÿ0-9]/u.test(b.textContent),
      })),
      punctuation,
      punctuation_inside_bdi: punctuation.filter(p => p.inside_bdi).length,
      document_overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    };
  });
}

async function shot(name, options = {}) {
  await page.screenshot({ path: path.join(dir, "screenshots", name), ...options });
}

async function shotBlock(name, hitId) {
  const detail = page.locator(`.source-detail[data-evidence-id="${hitId}"]`);
  await detail.scrollIntoViewIfNeeded();
  await detail.locator("blockquote").screenshot({ path: path.join(dir, "screenshots", name) });
}

async function openMobileSources() {
  const sources = page.getByRole("button", { name: "Fuentes", exact: true });
  if (await sources.isVisible()) await sources.click();
}

async function newInvestigation() {
  const button = page.getByRole("button", { name: /Nueva investigación/u }).first();
  if (await button.count() && await button.isVisible()) await button.click();
}

const cases = {};

try {
  await login();

  // ── A: Un Día en la Vida de un Jasid de Breslov, PDF 187 ────────────────
  const aQuestion = "¿Dónde aparece יְהִי רָצוֹן מִלְּפָנֶיךָ יְיָ אֱלֹהֵינוּ?";
  const a = await ask(aQuestion);
  write("a-query-api.json", { question: aQuestion, status: a.status, answer_markdown: a.body.answer_markdown, hits: a.body.hits?.map(h => ({ hit_id: h.hit_id, page: h.physical_pdf_page, work: h.work_title })) });
  const aHit = a.body.hits.find(h => h.chunk_id === "f741e872-1850-5bb7-8d73-a7e121f4084d");
  if (!aHit) throw new Error("A p187 chunk not returned by real retrieval");
  await selectEvidence(aHit.hit_id);
  const aDesktop = await blockquoteFacts(aHit.hit_id);
  aDesktop.matches_stored_display_snippet = normalize(aDesktop.text) === normalize(aHit.display_snippet);
  const dbPhrase = normalize(aHit.display_snippet).split(" ").slice(0, 4).join(" ");
  aDesktop.expected_phrase_present = aDesktop.text.includes(dbPhrase);
  aDesktop.expected_phrase = dbPhrase;
  aDesktop.no_artificial_spaces = aDesktop.bdis.every(b => !/[\u05d0-\u05ea]\s+[\u05b0-\u05c7\u0591-\u05c7]/u.test(b.text));
  cases.aDesktop = aDesktop;
  const aAnswer = await answerFacts();
  cases.aAnswer = aAnswer;
  write("a-p187-desktop.json", aDesktop);
  write("answer-markdown-a.json", aAnswer);
  await shot("a-p187-desktop.png", { fullPage: true });
  await shotBlock("a-p187-desktop-hebrew.png", aHit.hit_id);
  await page.locator(".enriched-markdown").last().scrollIntoViewIfNeeded();
  await page.locator(".enriched-markdown").last().screenshot({ path: path.join(dir, "screenshots", "a-answer-markdown.png") });

  // mobile smoke
  await page.setViewportSize({ width: 390, height: 844 });
  await openMobileSources();
  await selectEvidence(aHit.hit_id);
  const aMobile = await blockquoteFacts(aHit.hit_id);
  aMobile.matches_stored_display_snippet = normalize(aMobile.text) === normalize(aHit.display_snippet);
  aMobile.expected_phrase_present = aMobile.text.includes(dbPhrase);
  cases.aMobile = aMobile;
  write("a-p187-mobile.json", aMobile);
  await shot("a-p187-mobile.png");
  await shotBlock("a-p187-mobile-hebrew.png", aHit.hit_id);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.keyboard.press("Escape");
  await newInvestigation();

  // ── B: La Potencia de la Plegaria, PDF 416 ──────────────────────────────
  const bQuestion = "¿Dónde aparece NUMEROLOGÍA DE LAS LETRAS HEBREAS - GUEMATRIA?";
  const b = await ask(bQuestion);
  write("b-query-api.json", { question: bQuestion, status: b.status, answer_markdown: b.body.answer_markdown, hits: b.body.hits?.map(h => ({ hit_id: h.hit_id, page: h.physical_pdf_page, work: h.work_title })) });
  const bHit = b.body.hits.find(h => h.chunk_id === "9ad96286-7e98-5583-8e96-279e3603430a");
  if (!bHit) throw new Error("B p416 chunk not returned by real retrieval");
  await selectEvidence(bHit.hit_id);
  const bDesktop = await equationFacts(bHit.hit_id);
  bDesktop.matches_stored_display_snippet = normalize(bDesktop.block_text) === normalize(bHit.display_snippet);
  cases.bDesktop = bDesktop;
  const bAnswer = await answerFacts();
  cases.bAnswer = bAnswer;
  write("b-p416-desktop.json", bDesktop);
  write("answer-markdown-b.json", bAnswer);
  await shot("b-p416-desktop.png", { fullPage: true });
  await shotBlock("b-p416-desktop-equations.png", bHit.hit_id);

  await page.setViewportSize({ width: 390, height: 844 });
  await openMobileSources();
  await selectEvidence(bHit.hit_id);
  const bMobile = await equationFacts(bHit.hit_id);
  cases.bMobile = bMobile;
  write("b-p416-mobile.json", bMobile);
  await shot("b-p416-mobile.png");
  await shotBlock("b-p416-mobile-equations.png", bHit.hit_id);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.keyboard.press("Escape");

  // ── LTR regression on a Spanish-only real evidence block ───────────────
  const ltrHit = b.body.hits.find(h => !/[\u05d0-\u05ea\ufb1d-\ufb4f]/u.test(h.display_snippet ?? "") && /[A-Za-zÀ-ÖØ-öø-ÿ]/u.test(h.display_snippet ?? ""));
  if (!ltrHit) throw new Error("no LTR-only hit available for regression");
  await selectEvidence(ltrHit.hit_id);
  const ltrEvidence = await blockquoteFacts(ltrHit.hit_id);
  ltrEvidence.matches_stored_display_snippet = normalize(ltrEvidence.text) === normalize(ltrHit.display_snippet);
  cases.ltrEvidence = ltrEvidence;
  await shot("ltr-regression-evidence.png", { fullPage: true });

  await page.goto(`${BASE}/admin/content`);
  await page.locator("table").first().waitFor({ timeout: 60000 });
  const admin = await page.evaluate(() => {
    const html = document.documentElement;
    const table = document.querySelector("table");
    return {
      html_dir: html.getAttribute("dir"),
      body_direction: getComputedStyle(document.body).direction,
      table_direction: table ? getComputedStyle(table).direction : null,
      rtl_elements: document.querySelectorAll('[dir="rtl"]').length,
      bdi_count: document.querySelectorAll("bdi").length,
      document_overflow: html.scrollWidth > window.innerWidth + 1,
    };
  });
  cases.admin = admin;
  write("ltr-regression.json", { evidence_spanish_only: ltrEvidence, answer_spanish_only: bAnswer, admin });
  await shot("ltr-regression-admin.png", { fullPage: false });

  // ── Presentation forms (U+FB1D–U+FB4F) in a wholly Hebrew stored run ──
  await page.goto(`${BASE}/research`);
  await page.getByTestId("research-question").waitFor({ timeout: 60000 });
  const pQuestion = "¿Dónde aparece עיין ליקוטי מוהר״ן ח״א ריג אחר אתה סתר לי?";
  const p = await ask(pQuestion);
  write("presentation-query-api.json", { question: pQuestion, status: p.status, answer_markdown: p.body.answer_markdown, hits: p.body.hits?.map(h => ({ hit_id: h.hit_id, page: h.physical_pdf_page })) });
  const pTarget = p.body.hits.find(h => /[\ufb1d-\ufb4f]/u.test(h.display_snippet ?? "") && /[()]/u.test(h.display_snippet ?? ""));
  const targetP = pTarget?.hit_id;
  if (!targetP) throw new Error("presentation-form hit not available");
  await selectEvidence(targetP);
  const presentation = await blockquoteFacts(targetP);
  presentation.matches_stored_display_snippet = normalize(presentation.text) === normalize(pTarget.display_snippet);
  cases.presentation = presentation;
  const pAnswer = await answerFacts();
  cases.pAnswer = pAnswer;
  write("presentation-forms.json", { directionalt_source_text: presentation, answer_mixed_hebrew: aAnswer, answer_parentheses: pAnswer });
  await shot("presentation-forms-desktop.png", { fullPage: true });
  await shotBlock("presentation-forms-hebrew.png", targetP);
  await page.locator(".enriched-markdown").last().scrollIntoViewIfNeeded();
  await page.locator(".enriched-markdown").last().screenshot({ path: path.join(dir, "screenshots", "presentation-answer.png") });

  out.cases = Object.keys(cases);
} catch (error) {
  out.error = String(error?.stack ?? error);
  await shot("qa-error.png").catch(() => {});
} finally {
  write("browser-qa.json", out);
  await browser.close();
}

const cellOk = c => c.number_left_of_equals && c.equals_left_of_hebrew && c.same_visual_line && c.computed_white_space === "nowrap" && !c.overflows_cell;
const answerOk = a => Boolean(a) && a.bdis.every(b => b.dir === "auto" && !b.edge_punctuation && !b.leading_or_trailing_space && b.only_hebrew) && a.punctuation_inside_bdi === 0;
const summary = {
  error: out.error ?? null,
  console_errors: out.console_errors,
  http_errors: out.http_errors,
  a: cases.aDesktop && {
    stored_match: cases.aDesktop.matches_stored_display_snippet,
    phrase: cases.aDesktop.expected_phrase_present,
    presentation: cases.aDesktop.has_presentation_forms,
    bdi: cases.aDesktop.bdis.map(b => `${b.dir}/${b.computed_direction}`),
    overflow: cases.aDesktop.block_overflow,
    answer_ok: answerOk(cases.aAnswer),
    answer_paragraph_dir: cases.aAnswer?.paragraph_dir,
    answer_bdis: cases.aAnswer?.bdis.map(b => b.text.slice(0, 24)),
  },
  aMobile: cases.aMobile && { stored_match: cases.aMobile.matches_stored_display_snippet, phrase: cases.aMobile.expected_phrase_present, overflow: cases.aMobile.block_overflow, doc: cases.aMobile.document_overflow },
  b: cases.bDesktop && {
    stored_match: cases.bDesktop.matches_stored_display_snippet,
    cells: cases.bDesktop.cell_count,
    ok: cases.bDesktop.cells.every(cellOk),
    bad: cases.bDesktop.cells.filter(c => !cellOk(c)).map(c => c.text),
    doc_overflow: cases.bDesktop.document_overflow,
  },
  bMobile: cases.bMobile && {
    cells: cases.bMobile.cell_count,
    ok: cases.bMobile.cells.every(c => cellOk(c) && c.inside_viewport),
    bad: cases.bMobile.cells.filter(c => !(cellOk(c) && c.inside_viewport)).map(c => c.text),
    doc_overflow: cases.bMobile.document_overflow,
  },
  ltr: cases.ltrEvidence && {
    stored_match: cases.ltrEvidence.matches_stored_display_snippet,
    direction: cases.ltrEvidence.computed_direction,
    bdi: cases.ltrEvidence.bdis.map(b => `${b.dir}/${b.computed_direction}`),
    admin: cases.admin,
    answer_ok: answerOk(cases.bAnswer),
    answer_paragraph_dir: cases.bAnswer?.paragraph_dir,
    answer_bdi_count: cases.bAnswer?.bdi_count,
  },
  presentation: cases.presentation && {
    stored_match: cases.presentation.matches_stored_display_snippet,
    forms: cases.presentation.presentation_codepoints,
    bdi: cases.presentation.bdis.map(b => `${b.dir}/${b.computed_direction}`),
    overflow: cases.presentation.block_overflow,
    answer_mixed_ok: answerOk(cases.aAnswer),
    answer_parentheses_ok: answerOk(cases.pAnswer),
    answer_parentheses_paragraph_dir: cases.pAnswer?.paragraph_dir,
    answer_parentheses_bdis: cases.pAnswer?.bdis.map(b => b.text.slice(0, 24)),
  },
};
console.log(JSON.stringify(summary, null, 2));
