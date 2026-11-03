// Offline viewer only. No application server, login, API or corpus mutation.
// node data/reports/breslov/2026-10-01-clean-corpus-hebrew-ingestion-v1/validate-c-text-candidate.cjs
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '../../../..');
const { chromium } = require(path.join(root, 'SrvRestAstroLS_v1/astro/node_modules/@playwright/test'));
const out = path.join(__dirname, 'c-text-reconstruction-candidate');
(async () => {
  const browser = await chromium.launch({headless: true});
  const evidence = [];
  try {
    for (const [name, viewport] of [['desktop', {width:1440,height:1000}], ['mobile', {width:390,height:844}]]) {
      const page = await browser.newPage({viewport});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {if(message.type() === 'error') errors.push(message.text());});
      for (const pg of [2,41,55,56,143]) {
        await page.goto(pathToFileURL(path.join(out, `page-${pg}-viewer.html`)).href);
        const actual = await page.locator('p bdi').allTextContents();
        const expected = JSON.parse(fs.readFileSync(path.join(out, `page-${pg}-chars.json`))).lines.map(l => l.text);
        if(JSON.stringify(actual) !== JSON.stringify(expected)) throw Error('DOM text changed');
        await page.screenshot({path:path.join(out, `page-${pg}-${name}.png`),fullPage:false});
        const hebrewIndex = expected.findIndex(text => (text.match(/[\u05d0-\u05ea]/g) || []).length > 35);
        if (hebrewIndex >= 0) {
          await page.locator('p bdi').nth(hebrewIndex).scrollIntoViewIfNeeded();
          await page.screenshot({path:path.join(out, `page-${pg}-${name}-hebrew.png`),fullPage:false});
        }
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        evidence.push({page:pg,viewport:name,dom_codepoint_identity:true,horizontal_overflow:overflow,
          errors:[...errors],semantic_readability:'BLOCKED: unresolved canonical text and paragraph order'});
      }
      await page.close();
    }
  } finally { await browser.close(); }
  fs.writeFileSync(path.join(out,'browser-audit.json'),JSON.stringify({environment:'offline file viewer; Chromium',
    cases:evidence.length,production_modified:false,desktop_fidelity:'BLOCKED',mobile_fidelity:'BLOCKED',evidence},null,2));
  console.log(`Offline viewer: ${evidence.length} DOM identity checks passed; semantic desktop/mobile gates BLOCKED`);
})().catch(error => {console.error(error);process.exitCode=1;});
