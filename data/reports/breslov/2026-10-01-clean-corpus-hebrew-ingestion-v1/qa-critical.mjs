import {chromium,expect} from '../../../../SrvRestAstroLS_v1/astro/node_modules/@playwright/test/index.mjs';
import fs from 'node:fs';import {fileURLToPath} from 'node:url';
const dir=fileURLToPath(new URL('.',import.meta.url));const name=process.argv[2];
const book=JSON.parse(fs.readFileSync(dir+name+'-integrity.json'));
const data={a:{question:'¿Qué plegaria se dice antes de recitar תהלים en días de semana?',a:'יְהִי רָצוֹן מִלְּפָנֶיךָ',b:'אֲבוֹתֵינוּ',page:187,expected:'אֱלֹהֵינוּ'},b:{question:'¿Qué valores numéricos tienen las letras hebreas según la GUEMATRIA?',a:'6 = ו',b:'1 = א',page:416,expected:'6 = ו ; 1 = א'}}[name];
const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(60000);page.setDefaultNavigationTimeout(120000);
const report={case:name,actor:'viewer',mocked_responses:0,scope_overrides:0,console_errors:[],http_5xx:[]};
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text());});page.on('response',r=>{if(r.status()>=500)report.http_5xx.push({url:r.url(),status:r.status()});});
try{
 await page.goto('http://127.0.0.1:3008/login');await page.locator('#login-email').fill(process.env.TEBAAI_E2E_GUEST_EMAIL);await page.locator('#login-password').fill(process.env.TEBAAI_E2E_GUEST_PASSWORD);await page.getByRole('button',{name:'Ingresar',exact:true}).click();await page.waitForURL(/\/research\/?$/);
 await page.goto('http://127.0.0.1:3008/library/relation-qa/');await page.locator('input[type=checkbox]').uncheck();await page.locator('input[type=number]').fill('50');
 await page.getByTestId('relation-qa-question').fill(data.question);await page.getByPlaceholder('sangre',{exact:true}).fill(data.a);await page.getByPlaceholder('habla',{exact:true}).fill(data.b);
 const pending=page.waitForResponse(r=>r.url().endsWith('/library/relation-qa')&&r.request().method()==='POST',{timeout:180000});await page.getByTestId('relation-qa-submit').click();const response=await pending;expect(response.status()).toBe(200);const body=await response.json();fs.writeFileSync(dir+name+'-critical-api.json',JSON.stringify(body,null,2));
 const source=body.sources.find(s=>s.document_id===book.document_id&&s.page_number===data.page&&s.snippet.includes(data.expected));expect(source).toBeTruthy();
 const chunks=JSON.parse(fs.readFileSync(dir+name+'-chunks.json'));const chunk=chunks.find(c=>c.id===source.chunk_id);expect(chunk).toBeTruthy();
 expect(chunk.content.replace(/\s+/gu,' ').trim()).toContain(source.snippet.replace(/^…|…$/gu,'').trim());
 const snippet=page.locator('.italic').filter({hasText:source.snippet}).first();await expect(snippet).toBeVisible();await snippet.scrollIntoViewIfNeeded();expect(await snippet.textContent()).toBe(source.snippet);
 const cells=await snippet.locator('bdi').allTextContents();expect(cells.join('')).toBe(source.snippet);
 if(name==='a'){expect(source.snippet).not.toContain('יְהִ י');expect(source.snippet).not.toContain('אֱֹל');expect(source.snippet).not.toContain('ְֶך');}
 if(name==='b'){
  const equation=snippet.locator('bdi').filter({hasText:/^6 = ו$/u});
  expect(await equation.getAttribute('dir')).toBe('ltr');
  const positions=await equation.evaluate(el=>{
    const t=el.firstChild;const rect=(start,end)=>{const r=document.createRange();r.setStart(t,start);r.setEnd(t,end);return r.getBoundingClientRect().left;};
    return {number:rect(0,1),letter:rect(el.textContent.length-1,el.textContent.length)};
  });
  expect(positions.number).toBeLessThan(positions.letter);report.equation_visual_positions=positions;
  expect(cells).toContain('6 = ו');expect(cells).toContain('1 = א');expect(cells).toContain('80 = פ,ף');expect(cells).toContain('30 = ל');expect(source.snippet).not.toContain('ו1');expect(source.snippet).not.toContain('ת80');}
 await snippet.locator('..').screenshot({path:dir+name+'-critical-citation-desktop.png'});await page.screenshot({path:dir+name+'-critical-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await snippet.scrollIntoViewIfNeeded();await snippet.locator('..').screenshot({path:dir+name+'-critical-citation-mobile.png'});await page.screenshot({path:dir+name+'-critical-mobile.png',fullPage:true});
 report.source=source;report.cells=cells;report.api_equals_pg_and_dom=true;report.status='PASS';
 expect(report.console_errors).toEqual([]);expect(report.http_5xx).toEqual([]);
}catch(e){report.status='FAIL';report.error=e.message;await page.screenshot({path:dir+name+'-critical-error.png',fullPage:true});process.exitCode=1;}
finally{await browser.close();fs.writeFileSync(dir+name+'-critical-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify({case:name,status:report.status,error:report.error}));}
