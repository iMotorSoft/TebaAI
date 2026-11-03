import {chromium,expect} from '../../../../SrvRestAstroLS_v1/astro/node_modules/@playwright/test/index.mjs';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const dir=fileURLToPath(new URL('.',import.meta.url));
const caseName=process.argv[2];
const book=JSON.parse(fs.readFileSync(dir+caseName+'-integrity.json'));
const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(60000);page.setDefaultNavigationTimeout(120000);
const report={case:caseName,actor:'viewer',mocked_responses:0,scope_overrides:0,queries:[],console_errors:[],http_5xx:[]};
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text());});
page.on('response',r=>{if(r.status()>=500)report.http_5xx.push({url:r.url(),status:r.status()});});
const questions={
 a:[['literal','יְהִי רָצוֹן מִלְּפָנֶיךָ'],['semantic','¿Qué plegaria se dice antes de recitar תהלים en días de semana?']],
 b:[['literal','GUEMATRIA'],['semantic','¿Qué valores numéricos tienen las letras hebreas en La Potencia de la Plegaria?']],
 c:[['literal','CONSTRUYENDO UN MISHKÁN en Likutey Halajot'],['semantic','¿Cómo puede una persona encontrar la bondad dentro de sí misma según Likutey Halajot?'],['hebrew','שמע ישראל en Likutey Halajot'],['reference','Salmos 16:1 en Likutey Halajot'],['negative','¿Cuál es la contraseña secreta del satélite TEBAAI-ZX932?']]
}[caseName];
try{
 await page.goto('http://127.0.0.1:3008/login');
 await page.locator('#login-email').fill(process.env.TEBAAI_E2E_GUEST_EMAIL);
 await page.locator('#login-password').fill(process.env.TEBAAI_E2E_GUEST_PASSWORD);
 await page.getByRole('button',{name:'Ingresar',exact:true}).click();
 await page.waitForURL(/\/research\/?$/);
 for(const [kind,question] of questions){
  await page.goto('http://127.0.0.1:3008/research');
  await page.getByTestId('research-question').fill(question);
  const pending=page.waitForResponse(r=>r.url().endsWith('/library/investigative-qa/v1')&&r.request().method()==='POST'&&!r.request().postDataJSON()?.phase,{timeout:180000});
  await page.getByTestId('research-submit').click();
  const response=await pending;expect(response.status()).toBe(200);
  const body=await response.json();fs.writeFileSync(dir+caseName+'-'+kind+'-api.json',JSON.stringify(body,null,2));
  await expect(page.getByTestId('research-result-heading')).toBeVisible({timeout:120000});
  expect(body.retrieval.semantic_status).toBe('ok');
  const hits=(body.hits||[]).filter(h=>h.document_id===book.document_id);
  if(kind!=='negative')expect(hits.length).toBeGreaterThan(0);
  await page.screenshot({path:dir+caseName+'-'+kind+'-desktop.png',fullPage:true});
  if(hits.length){
   const hit=hits.find(h=>h.pdf_page===(caseName==='a'?187:caseName==='b'?416:55)&&/יְהִי|GUEMATR|Salmos/u.test(h.quote||''))||hits[0];
   const id=hit.hit_id||hit.evidence_id;
   const button=page.locator(`.source-list button[data-evidence-id="${id}"]`).first();
   if(await button.count()) {
     if(!await button.isVisible()) {
       const detail=button.locator('xpath=ancestor::details[1]');
       if(await detail.count())await detail.locator('summary').first().click();
     }
     await button.click();
   }
   const preview=page.locator('.source-detail').first();
   await preview.scrollIntoViewIfNeeded();
   await preview.screenshot({path:dir+caseName+'-'+kind+'-preview-desktop.png'});
   await page.screenshot({path:dir+caseName+'-'+kind+'-source-desktop.png',fullPage:true});
  }
  await page.setViewportSize({width:390,height:844});
  const sources=page.getByRole('button',{name:'Fuentes',exact:true});
  if(await sources.count())await sources.click();
  await page.screenshot({path:dir+caseName+'-'+kind+'-source-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  report.queries.push({kind,question,status:'PASS',research_status:body.research_status,
    hits:hits.map(h=>({document_id:h.document_id,page:h.pdf_page,printed_page:h.printed_page,chunk_id:h.chunk_id,evidence_id:h.hit_id,quote:h.quote,is_primary:h.is_primary})),retrieval:body.retrieval});
 }
 expect(report.console_errors).toEqual([]);expect(report.http_5xx).toEqual([]);
 report.status='PASS';
}catch(e){report.status='FAIL';report.error=e.message;await page.screenshot({path:dir+caseName+'-qa-error.png',fullPage:true});process.exitCode=1;}
finally{await browser.close();fs.writeFileSync(dir+caseName+'-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify({case:caseName,status:report.status,error:report.error,queries:report.queries.map(q=>({kind:q.kind,hits:q.hits?.length}))}));}
