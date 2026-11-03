import { chromium, expect } from '../../../../SrvRestAstroLS_v1/astro/node_modules/@playwright/test/index.mjs';
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
const dir = fileURLToPath(new URL('.', import.meta.url));
const phase = process.argv[2];
const base = 'http://127.0.0.1:3008';
const report = {phase, base, mocked_responses:0, scope_overrides:0, console_errors:[], http_5xx:[], started_at:new Date().toISOString()};
const browser = await chromium.launch();
const page = await browser.newPage({viewport:{width:1440,height:900}});
page.setDefaultTimeout(60000);
page.setDefaultNavigationTimeout(120000);
page.on('console', m => {if(m.type()==='error') report.console_errors.push(m.text());});
page.on('response', r => {if(r.status()>=500) report.http_5xx.push({url:r.url(),status:r.status()});});
const save = (name,value)=>fs.writeFileSync(dir+name,JSON.stringify(value,null,2));
try {
  await page.goto(base+'/login');
  await page.locator('#login-email').fill(process.env.TEBAAI_E2E_ADMIN_EMAIL);
  await page.locator('#login-password').fill(process.env.TEBAAI_E2E_ADMIN_PASSWORD);
  await page.getByRole('button',{name:'Ingresar',exact:true}).click();
  await page.waitForURL(/\/research\/?$/);
  await page.goto(base+'/admin/content');
  await expect(page.getByRole('heading',{name:'Gestor de Contenidos',exact:true})).toBeVisible();
  if(phase==='zero') {
    await expect(page.getByText('Todavía no hay contenidos incorporados',{exact:true})).toBeVisible();
    await page.screenshot({path:dir+'corpus-zero-desktop.png',fullPage:true});
    const reset=JSON.parse(fs.readFileSync(dir+(fs.existsSync(dir+'niqqud-retest-reset-result.json')?'niqqud-retest-reset-result.json':'total-dev-reset-result.json')));
    expect(reset.gate).toBe('CORPUS_ZERO_DATA_VERIFIED');
    report.gate='TEBAAI_DEV_DOCUMENT_CORPUS_ZERO_PASS';
    report.auth_works=true;
  } else {
    const zero=JSON.parse(fs.readFileSync(dir+'ui-zero.json'));
    expect(zero.gate).toBe('TEBAAI_DEV_DOCUMENT_CORPUS_ZERO_PASS');
    const book=JSON.parse(fs.readFileSync(dir+'source-books.json')).find(b=>b.label.toLowerCase()===phase);
    if(!book) throw Error('Unknown authorized book');
    if(phase!=='a') {
      const previous=phase==='b'?'a':'b';
      const validation=JSON.parse(fs.readFileSync(dir+previous+'-validation.json'));
      expect(validation.status).toBe('PASS');
    }
    if(fs.existsSync(dir+phase+'-job-created.json')) throw Error('Already uploaded: resume through UI, never duplicate blindly');
    const bytes=fs.readFileSync(book.source_path);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(book.sha256);
    expect(bytes.length).toBe(book.size_bytes);
    report.source=book;
    await page.getByRole('button',{name:'＋ Nueva carga',exact:true}).click();
    const uploadPending=page.waitForResponse(r=>r.url().includes('/admin/content/uploads')&&r.request().method()==='POST');
    await page.locator('#cm-file-input').setInputFiles(book.source_path);
    const upload=await uploadPending;
    expect(upload.status()).toBeLessThan(300);
    const uploaded=await upload.json();save(phase+'-ui-upload.json',uploaded);
    expect(uploaded.page_count).toBe(book.pages);
    await expect(page.getByText('Archivo válido',{exact:true})).toBeVisible();
    await page.screenshot({path:dir+phase+'-upload.png',fullPage:true});
    await page.getByRole('button',{name:'Continuar',exact:true}).click();
    await page.getByLabel('Título de la obra').fill(book.title);
    await page.getByLabel('Idioma principal').selectOption('es');
    await page.getByLabel('Familia documental (opcional)').fill(phase==='c'?'Likutey Halajot':'Breslov');
    await page.getByRole('button',{name:'Continuar a confirmación',exact:true}).click();
    await page.screenshot({path:dir+phase+'-confirmation.png',fullPage:true});
    const pending=page.waitForResponse(r=>r.url().includes('/admin/content/jobs')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Iniciar procesamiento',exact:true}).click();
    const created=await pending;
    expect(created.status()).toBeLessThan(300);
    const job=await created.json();save(phase+'-job-created.json',job);
    expect(job.status).toBe('queued');report.job_id=job.job_id;
    page.on('response',async r=>{
      if(r.url().includes('/admin/content/jobs/'+job.job_id)&&r.request().method()==='GET'&&r.status()===200) {
        const j=await r.json();save(phase+'-job-observed.json',j);
      }
    });
    await expect(page.getByRole('heading',{name:/Documento procesado/})).toBeVisible({timeout:1200000});
    await page.screenshot({path:dir+phase+'-candidate.png',fullPage:true});
    await page.getByRole('button',{name:'Abrir diagnóstico',exact:true}).click();
    await page.getByRole('button',{name:'Publicar para consulta',exact:true}).click();
    await page.screenshot({path:dir+phase+'-publication-confirmation.png',fullPage:true});
    const publishPending=page.waitForResponse(r=>r.url().includes('/publish')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Confirmar publicación',exact:true}).click();
    const published=await publishPending;
    const publication=await published.json();save(phase+'-publication.json',publication);
    expect(published.status()).toBe(200);
    await expect(page.getByText('Documento publicado. Ya forma parte del corpus consultable.',{exact:true})).toBeVisible();
    await page.screenshot({path:dir+phase+'-ready.png',fullPage:true});
    report.publication=publication;
    report.ingestion='UI_ONLY';
  }
  expect(report.console_errors).toEqual([]);expect(report.http_5xx).toEqual([]);
  report.status='PASS';
} catch(error) {
  report.status='FAIL';report.error=error.message;
  await page.screenshot({path:dir+'ui-'+phase+'-error.png',fullPage:true});
  process.exitCode=1;
} finally {
  report.finished_at=new Date().toISOString();save('ui-'+phase+'.json',report);
  await browser.close();console.log(JSON.stringify({phase,status:report.status,error:report.error,gate:report.gate,job_id:report.job_id}));
}
