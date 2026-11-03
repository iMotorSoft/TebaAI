import {chromium} from '../../../../SrvRestAstroLS_v1/astro/node_modules/@playwright/test/index.mjs';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';
const dir=fileURLToPath(new URL('.',import.meta.url));
const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1600,height:1000}});
const out={url:'https://breslov.tebaai.live',console_errors:[],http_errors:[],cases:[]};
page.on('console',m=>{if(m.type()==='error')out.console_errors.push(m.text())});page.on('response',r=>{if(r.status()>=500)out.http_errors.push({url:r.url(),status:r.status()})});
try{
 await page.goto(out.url+'/login/');await page.locator('#login-email').fill(process.env.TEBAAI_E2E_ADMIN_EMAIL);await page.locator('#login-password').fill(process.env.TEBAAI_E2E_ADMIN_PASSWORD);await page.getByRole('button',{name:'Ingresar',exact:true}).click();await page.getByTestId('research-question').waitFor({timeout:30000});
 for(const [name,question] of [['natural','¿Dónde aparece יהי רצון שאומרים קודם אמירת תהלים בימות החול?'],['numbers','¿Dónde aparece NUMEROLOGÍA DE LAS LETRAS HEBREAS - GUEMATRIA?']]){
  const pending=page.waitForResponse(r=>r.url().includes('/library/investigative-qa/v1')&&r.request().method()==='POST'&&!r.request().postDataJSON()?.phase,{timeout:180000});
  await page.getByTestId('research-question').fill(question);await page.getByTestId('research-submit').click();const analyze=page.getByTestId('interpretation-analyze');
  await Promise.race([pending,analyze.waitFor({state:'visible',timeout:180000}).then(()=>analyze.click())]);const r=await pending;const body=await r.json();fs.writeFileSync(dir+'/'+name+'-browser-api.json',JSON.stringify(body,null,2));await page.waitForTimeout(1500);
  const hits=body.hits?.filter(h=>/[א-ת]/u.test(h.quote||h.paragraph_text||h.snippet||''))||[];const target=hits.find(h=>h.chunk_id===(name==='natural'?'045c39b8-4e46-400c-99f8-31f0fcff4c7f':'b29a1432-2a34-422e-a748-d6174a94008f'))||hits[0];
  if(target){const button=page.locator(`.source-list button[data-evidence-id="${target.hit_id}"]`).first();if(await button.count()){const details=button.locator('xpath=ancestor::details[1]');if(await details.count())await details.locator('summary').click();await button.click();await page.locator('.source-detail').evaluate(e=>e.scrollIntoView({block:'start'}));}}
  const elements=await page.locator('.source-detail blockquote,.enriched-markdown p,.enriched-markdown blockquote,.primary-evidence blockquote,.synthesis p,.works-results button>span').evaluateAll(els=>els.filter(e=>/[א-ת]/u.test(e.textContent||'')).map(e=>{const s=getComputedStyle(e);return {tag:e.tagName,text:e.textContent,dir:e.getAttribute('dir'),lang:e.getAttribute('lang'),direction:s.direction,unicodeBidi:s.unicodeBidi,fontStyle:s.fontStyle,overflow:e.scrollWidth>e.clientWidth+1}}));
  out.cases.push({name,question,http_status:r.status(),status:body.status,target,elements,execution:body.execution});await page.screenshot({path:dir+'/'+name+'-desktop.png',fullPage:true});
  if(name==='natural'){await page.setViewportSize({width:390,height:844});const sources=page.getByRole('button',{name:'Fuentes',exact:true});if(await sources.isVisible())await sources.click();await page.screenshot({path:dir+'/natural-mobile.png',fullPage:true});await page.setViewportSize({width:1600,height:1000});}
  await page.getByRole('button',{name:/Nueva investigación/}).first().click();
 }
}catch(e){out.error=e.message;await page.screenshot({path:dir+'/error.png',fullPage:true});}
fs.writeFileSync(dir+'/browser.json',JSON.stringify(out,null,2));await browser.close();console.log(JSON.stringify({cases:out.cases.map(c=>({name:c.name,status:c.status,hebrew_elements:c.elements.length})),error:out.error}));
