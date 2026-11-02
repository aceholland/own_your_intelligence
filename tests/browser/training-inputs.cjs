// Run against a temporary Own instance, never a production/business dataset.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const origin=process.env.OWN_TEST_URL||'http://127.0.0.1:8766';

async function seed(page){
  const boot=await (await page.request.get(origin+'/api/bootstrap')).json();
  const post=async(path,data)=>{
    const response=await page.request.post(origin+path,{data,headers:{'X-Own-Token':boot.csrf_token}});
    assert(response.ok(),await response.text());return response.json();
  };
  const ws=await post('/api/workspaces',{name:'Browser regression · fictional'});
  const job=await post(`/api/workspaces/${ws.id}/jobs`,{name:'Input preservation',goal:'Answer briefly'});
  await post(`/api/workspaces/${ws.id}/jobs/${job.id}/examples`,{kind:'teach',input:'A request',output:'A good response'});
  await page.goto(`${origin}/#w/${ws.id}/j/${job.id}/teach`);
  await page.getByRole('button',{name:'Review or edit all examples',exact:true}).waitFor();
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  const results=[];
  for(const [name,test] of [
    ['dirty instructions survive example-review action',async page=>{
      await page.getByLabel('Anything it should always remember?').fill('UNSAVED INSTRUCTIONS MUST SURVIVE');
      await page.getByRole('button',{name:'Review or edit all examples',exact:true}).click();
      assert.equal(await page.locator('#dialog').evaluate(e=>e.open),false,'Save instructions first; do not open an edit flow that can replace the dirty form.');
      assert.equal(await page.getByLabel('Anything it should always remember?').inputValue(),'UNSAVED INSTRUCTIONS MUST SURVIVE');
      assert.match(await page.locator('[data-form="instructions"] .form-errors').innerText(),/Save your instructions/);
    }],
    ['late save cannot close a replacement modal',async page=>{
      await page.getByRole('button',{name:'Review or edit all examples',exact:true}).click();
      await page.getByRole('button',{name:'Edit',exact:true}).click();
      await page.getByLabel('A good answer',{exact:true}).fill('A better saved response');
      let release;
      const pending=new Promise(resolve=>{release=resolve});
      await page.route('**/examples/*',async route=>{await pending;await route.continue()});
      const request=page.waitForRequest(r=>r.method()==='PATCH'&&r.url().includes('/examples/'));
      await page.getByRole('button',{name:'Save example',exact:true}).click();
      await request;
      await page.keyboard.press('Escape');
      await page.getByRole('button',{name:'Add a teaching example',exact:true}).click();
      await page.getByLabel('Someone asks…',{exact:true}).fill('NEW UNSAVED REQUEST');
      await page.getByLabel('What would a good answer be?',{exact:true}).fill('NEW UNSAVED ANSWER');
      const finished=page.waitForEvent('requestfinished',r=>r.method()==='PATCH'&&r.url().includes('/examples/'));
      release();await finished;
      // Allow the old response's JSON/body/handler microtasks to settle.
      await page.waitForTimeout(350);
      assert.equal(await page.locator('#dialog').evaluate(e=>e.open),true,'The old save must not close the replacement modal.');
      assert.equal(await page.getByLabel('Someone asks…',{exact:true}).inputValue(),'NEW UNSAVED REQUEST');
      assert.equal(await page.getByLabel('What would a good answer be?',{exact:true}).inputValue(),'NEW UNSAVED ANSWER');
    }]
  ]){
    const page=await browser.newPage();
    try{await seed(page);await test(page);results.push({name,passed:true})}
    catch(error){results.push({name,passed:false,error:error.message})}
    finally{await page.close()}
  }
  await browser.close();
  console.log(JSON.stringify(results,null,2));
  if(results.some(result=>!result.passed))process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1});
