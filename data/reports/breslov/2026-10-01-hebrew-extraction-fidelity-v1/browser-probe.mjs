import { chromium, expect } from '../../../../SrvRestAstroLS_v1/astro/node_modules/@playwright/test/index.mjs';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const dir = fileURLToPath(new URL('.', import.meta.url));
const baseURL = 'http://127.0.0.1:3008';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
page.setDefaultNavigationTimeout(120000);
const report = { baseURL, api: '/library/relation-qa', scope: 'breslov_e2e', request_scope_override: true, mocked_responses: 0, console_errors: [], http_5xx: [], cases: [] };
page.on('console', m => { if (m.type() === 'error') report.console_errors.push(m.text()); });
page.on('response', r => { if (r.status() >= 500) report.http_5xx.push({ url: r.url(), status: r.status() }); });
// The existing Relation QA API accepts an authorized scope. The UI's default
// is primary; this DEV probe supplies the isolated scope on its real request.
await page.route('**/library/relation-qa', async route => {
  if (route.request().method() !== 'POST') return route.continue();
  const body = route.request().postDataJSON();
  await route.continue({ postData: JSON.stringify({ ...body, knowledge_scope_code: 'breslov_e2e', include_test_candidates: true, evidence_depth: 'full', top_k: 50 }) });
});
try {
  await page.goto(baseURL + '/login/');
  await page.locator('#login-email').fill(process.env.TEBAAI_E2E_ADMIN_EMAIL);
  await page.locator('#login-password').fill(process.env.TEBAAI_E2E_ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Ingresar', exact: true }).click();
  await page.getByTestId('research-question').waitFor({ timeout: 60000 });
  for (const data of [
    { name: 'a', question: '¿Qué plegaria se dice antes de recitar תהלים en días de semana?', a: 'יְהִי רָצוֹן מִלְּפָנֶיָך', b: 'אֲבוֹתֵינוּ', pdf_page: 187, expected: 'יְהִי רָצוֹן' },
    { name: 'b', question: '¿Qué valores numéricos tienen las letras hebreas según la GUEMATRIA?', a: '6 = ו', b: '1 = א', pdf_page: 416, expected: '6 = ו ; 1 = א' },
  ].filter(c => !process.argv.includes('--case=a') || c.name === 'a')) {
    const job = JSON.parse(fs.readFileSync(dir + data.name + '-job-final.json'));
    await page.goto(baseURL + '/library/relation-qa/');
    await page.locator('input[type=checkbox]').uncheck();
    await page.getByTestId('relation-qa-question').fill(data.question);
    await page.getByPlaceholder('sangre', { exact: true }).fill(data.a);
    await page.getByPlaceholder('habla', { exact: true }).fill(data.b);
    const pending = page.waitForResponse(r => r.url().includes('/library/relation-qa') && r.request().method() === 'POST', { timeout: 180000 });
    await page.getByTestId('relation-qa-submit').click();
    const response = await pending;
    expect(response.status()).toBe(200);
    const body = await response.json();
    fs.writeFileSync(dir + data.name + '-api.json', JSON.stringify(body, null, 2));
    const source = body.sources.find(s => s.document_id === job.document_id && s.page_number === data.pdf_page && s.snippet.includes(data.expected));
    expect(source, 'corrected source and physical PDF page from live API').toBeTruthy();
    expect(source.snippet).not.toContain(data.name === 'a' ? 'יְהִ י' : 'ו1');
    const chunks = JSON.parse(fs.readFileSync(dir + data.name + '-chunks.json'));
    const chunk = chunks.find(c => c.id === source.chunk_id);
    expect(chunk).toBeTruthy();
    const normalizedChunk = chunk.content.replace(/\s+/gu, ' ').trim();
    expect(normalizedChunk).toContain(source.snippet.replace(/^…|…$/gu, '').trim());
    const snippet = page.locator('.italic').filter({ hasText: source.snippet }).first();
    await expect(snippet).toBeVisible({ timeout: 30000 });
    await snippet.scrollIntoViewIfNeeded();
    const cells = await snippet.locator('bdi').allTextContents();
    expect(cells.join('')).toBe(source.snippet);
    if (data.name === 'b') {
      expect(cells).toContain('6 = ו');
      expect(cells).toContain('1 = א');
      expect(cells).toContain('80 = פ,ף');
      expect(cells).toContain('30 = ל');
    }
    const dom = await snippet.textContent();
    expect(dom).toBe(source.snippet);
    const heading = page.getByRole('heading', { name: 'Respuesta editorial', exact: true });
    await expect(heading).toBeVisible();
    const answer = heading.locator('..').locator('.prose');
    expect(await answer.textContent()).toBe(body.answer.editorial_answer_markdown);
    expect(body.answer.editorial_answer_markdown).toContain('p. ' + data.pdf_page);
    await heading.locator('..').screenshot({ path: dir + data.name + '-answer-desktop.png' });
    await snippet.locator('..').screenshot({ path: dir + data.name + '-citation-desktop.png' });
    await page.screenshot({ path: dir + data.name + '-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await snippet.scrollIntoViewIfNeeded();
    await snippet.locator('..').screenshot({ path: dir + data.name + '-citation-mobile.png' });
    await page.screenshot({ path: dir + data.name + '-mobile.png', fullPage: true });
    report.cases.push({ name: data.name, status: 'PASS', pdf_page: source.page_number, document_id: source.document_id, chunk_id: source.chunk_id, api_equals_DOM: dom === source.snippet, api_matches_pg_excerpt: true, isolated_cells: cells, answer_API_equals_DOM: true, snippet: source.snippet, method: body.method });
    await page.setViewportSize({ width: 1600, height: 1000 });
  }
  expect(report.console_errors).toEqual([]);
  expect(report.http_5xx).toEqual([]);
} catch (error) {
  report.error = error.message;
  await page.screenshot({ path: dir + 'browser-error.png', fullPage: true });
  process.exitCode = 1;
} finally {
  fs.writeFileSync(dir + (process.argv.includes('--case=a') ? 'browser-a.json' : 'browser.json'), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify({ cases: report.cases.map(c => ({ name: c.name, status: c.status })), error: report.error }));
}
