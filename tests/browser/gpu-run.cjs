// Controlled browser fixtures only. All mutations are intercepted; no Modal calls or real training.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const origin=process.env.OWN_TEST_URL||'http://127.0.0.1:8765';
const jobRoute=process.env.OWN_TEST_JOB||'#w/dff830bc6e34461ab7d009b10a9cec53/j/ae0d277606b247188e5b4732f9411e71/gpu';
const output=process.env.OWN_TEST_OUTPUT||process.cwd();
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900},acceptDownloads:true});
  const errors=[],mutations=[];page.on('pageerror',error=>errors.push(error.message));
  let runs=[],runNumber=0,delayed=null;
  await page.route('**/api/**',async route=>{
    const request=route.request(),url=new URL(request.url()),method=request.method();
    const fulfill=value=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(value)});
    if(url.pathname==='/api/gpu'&&method==='GET')return fulfill({sdk:{status:'ready'},connected:true,busy:runs.some(r=>['queued','running','stopping'].includes(r.status)),credential_storage:'Controlled test response',remote_training_enabled:true,billing_verified:false});
    if(/^\/api\/workspaces\/[^/]+\/jobs\/[^/]+$/.test(url.pathname)&&method==='GET'){
      const response=await route.fetch(),value=await response.json();return fulfill({...value,gpu_runs:runs});
    }
    if(method==='POST'){
      mutations.push(url.pathname);
      if(url.pathname.endsWith('/gpu/runs')){
        const body=request.postDataJSON();
        for(const field of ['upload','free_only','zero_limit','credits'])assert.equal(body[field],true);
        if(delayed)await delayed.gate;
        const run={id:'controlled-run-'+(++runNumber),status:'queued',phase:'Preparing the GPU job',step:0,total_steps:18,created_at:new Date().toISOString(),dataset_hash:body.dataset_hash,results:[],base:{id:'Qwen/Qwen3-4B-Instruct-2507'},quote:{region:'us'},download_available:false};
        runs.unshift(run);return fulfill(run);
      }
      if(url.pathname.endsWith('/review')){const body=request.postDataJSON();runs[0].results[0].review=body.review;return fulfill(runs[0]);}
      if(url.pathname.endsWith('/reconnect')){runs[0].status='stopping';runs[0].phase='Checking and stopping the cloud job';return fulfill(runs[0]);}
      if(url.pathname.endsWith('/cancel')){runs[0].status='stopping';runs[0].phase='Asking Modal to stop the cloud job';return fulfill(runs[0]);}
      throw Error('Unexpected mutation blocked: '+url.pathname);
    }
    if(url.pathname.endsWith('/export')&&url.pathname.includes('/gpu/runs/'))return route.fulfill({status:200,contentType:'application/zip',body:Buffer.from('controlled download fixture')});
    return route.continue();
  });
  try{
    await page.goto(origin+'/'+jobRoute);
    await page.getByRole('heading',{name:'Train a stronger business AI.',exact:true}).waitFor();
    await page.getByRole('button',{name:'Train on GPU',exact:true}).click();
    await page.getByRole('button',{name:'Start with free credits',exact:true}).click();
    assert.equal(mutations.length,0);
    assert.equal(await page.locator('#gpu-upload').getAttribute('aria-invalid'),'true');
    for(const id of ['gpu-upload','gpu-free_only','gpu-zero_limit','gpu-credits'])await page.locator('#'+id).check();
    await page.getByRole('button',{name:'Start with free credits',exact:true}).click();
    await page.locator('#dialog').waitFor({state:'hidden'});
    await page.getByText('0 of 18 steps',{exact:true}).waitFor();
    runs[0]={...runs[0],status:'running',phase:'Learning your examples',step:5};
    await page.getByText('5 of 18 steps',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Stop cloud job',exact:true}).click();
    await page.getByRole('button',{name:'Stopping…',exact:true}).waitFor();
    runs[0]={...runs[0],status:'interrupted',phase:'Cloud stop unconfirmed',error:'Controlled connection loss. Stop is unconfirmed.',provider_workspace_name:'fictional-workspace'};
    await page.getByText('Controlled connection loss. Stop is unconfirmed.',{exact:true}).waitFor();
    assert(await page.getByRole('button',{name:'Stop cloud job',exact:true}).isEnabled());
    await page.getByRole('button',{name:'Reconnect to stop',exact:true}).click();
    await page.getByLabel('Token ID',{exact:true}).fill('ak-controlled-fixture');
    await page.getByLabel('Token secret',{exact:true}).fill('as-controlled-fixture');
    await page.getByRole('button',{name:'Connect and stop cloud job',exact:true}).click();
    await page.locator('#dialog').waitFor({state:'hidden'});
    await page.getByRole('button',{name:'Stopping…',exact:true}).waitFor();
    runs[0]={...runs[0],status:'complete',phase:'Ready for your review',step:18,download_available:true,changed_parameters:184320,first_loss:2,last_loss:1,
      results:[{check_id:'held-out',input:'When will my order arrive?',expected:'Five working days.',before:'I am not sure.',after:'Your order arrives in five working days.',before_error:null,error:null,review:'pending'}]};
    await page.reload();
    await page.getByText('Your order arrives in five working days.',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Use this training',exact:true}).count(),0);
    await page.getByRole('button',{name:'Looks right',exact:true}).click();
    await page.locator('[data-action="gpu-review"][data-review="pass"][aria-pressed="true"]').waitFor();
    await page.getByRole('button',{name:'Looks right',exact:true}).getAttribute('aria-pressed').then(value=>assert.equal(value,'true'));
    await page.getByRole('button',{name:'Download GPU model',exact:true}).click();
    const download=page.waitForEvent('download');
    await page.getByRole('button',{name:'Download private model',exact:true}).click();
    await (await download).saveAs(path.join(output,'controlled-gpu-model.zip'));
    await page.locator('#dialog').waitFor({state:'hidden'});
    // Late launch response must preserve a new modal and its input.
    await page.getByRole('button',{name:'Train on GPU',exact:true}).click();
    for(const id of ['gpu-upload','gpu-free_only','gpu-zero_limit','gpu-credits'])await page.locator('#'+id).check();
    let release;delayed={gate:new Promise(resolve=>{release=resolve})};
    const pending=page.waitForRequest(r=>r.url().endsWith('/gpu/runs')&&r.method()==='POST');
    await page.getByRole('button',{name:'Start with free credits',exact:true}).click();await pending;
    await page.keyboard.press('Escape');
    await page.getByText('Account and portable setup',{exact:true}).click();
    await page.getByRole('button',{name:'Prepare training package',exact:true}).click();
    await page.getByLabel('Planning allowance (USD)',{exact:true}).fill('3.00');
    const finished=page.waitForEvent('requestfinished',r=>r.url().endsWith('/gpu/runs')&&r.method()==='POST');
    release();await finished;await page.waitForTimeout(200);
    assert.equal(await page.locator('#dialog').evaluate(e=>e.open),true);
    assert.equal(await page.getByLabel('Planning allowance (USD)',{exact:true}).inputValue(),'3.00');
    await page.keyboard.press('Escape');
    runs=runs.filter(run=>run.status==='complete');await page.reload();
    await page.getByText('Your order arrives in five working days.',{exact:true}).waitFor();
    await page.locator('#toast').waitFor({state:'hidden',timeout:10000});
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:path.join(output,'step4-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(output,'step4-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({fixtureOnly:true,cloudCalls:0,consentGate:true,measuredProgress:true,stopUnconfirmed:true,humanReview:true,download:true,lateModalPreserved:true,mobileWidth:390,errors}));
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
