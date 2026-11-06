// Run against a temporary Own instance. The result contains synthetic test weights.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const fs=require('node:fs/promises');
const path=require('node:path');

const origin=process.env.OWN_TEST_URL||'http://127.0.0.1:8766';
const root=path.resolve(__dirname,'../..');
const teachingAnswer='Standard delivery takes five working days.';
const checkRequest='When should I expect my package?';
const expectedAnswer='Expected by the business: five working days.';

async function seed(page) {
  const boot=await (await page.request.get(origin+'/api/bootstrap')).json();
  const post=async (route,data)=>{
    const response=await page.request.post(origin+route,{data,headers:{'X-Own-Token':boot.csrf_token}});
    assert(response.ok(),await response.text());
    return response.json();
  };
  const ws=await post('/api/workspaces',{name:'Colab browser test · fictional'});
  const job=await post(`/api/workspaces/${ws.id}/jobs`,{name:'Fictional shop delivery',goal:'Explain the shop policy briefly.'});
  const jobPath=`/api/workspaces/${ws.id}/jobs/${job.id}`;
  for(const input of ['How long is standard delivery?','When will it arrive?','How many days does regular shipping take?']){
    await post(jobPath+'/examples',{kind:'teach',input,output:teachingAnswer});
  }
  await post(jobPath+'/examples',{kind:'check',input:checkRequest,output:expectedAnswer});
  return `/#w/${ws.id}/j/${job.id}/train`;
}

async function makeResult(download) {
  const filename=await download.path();
  const notebook=await fs.readFile(filename,'utf8');
  assert(notebook.includes(teachingAnswer));
  assert(notebook.includes(checkRequest));
  assert(!notebook.includes(expectedAnswer),'Expected answers must stay out of the cloud notebook.');
  const python=String.raw`
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, 'tests')
from test_gpu_result import fixture

nb = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        if any(line.startswith('payload = json.loads(') for line in source.splitlines()):
            payload = json.loads(ast.literal_eval(ast.parse(source).body[0].value.args[0]))
            break
else:
    raise RuntimeError('Missing frozen payload')
results = [
    dict(check_id=check['id'], input=check['input'], before='It may take 5–7 working days.',
         after='It takes five working days.', before_error=None, error=None)
    for check in payload['checks']
]
data, _ = fixture({'results': results}, payload=payload)
sys.stdout.buffer.write(data)
`;
  const generated=spawnSync(process.env.OWN_TEST_PYTHON||'python',['-c',python,filename],{
    cwd:root,maxBuffer:64*1024*1024,windowsHide:true
  });
  assert.ifError(generated.error);
  assert.equal(generated.status,0,generated.stderr.toString());
  return generated.stdout;
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1280,height:900},acceptDownloads:true});
    page.setDefaultTimeout(12000);
    const errors=[];
    const external=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',route=>{
      const url=new URL(route.request().url());
      if(url.origin===origin)return route.continue();
      external.push(url.origin);
      return route.abort();
    });
    await page.goto(origin+await seed(page));
    await page.getByRole('heading',{name:'Train in Colab',exact:true}).waitFor();
    await page.getByRole('button',{name:'Prepare notebook',exact:true}).click();
    const dialog=page.getByRole('dialog');
    const consent=dialog.getByRole('checkbox',{name:'I have permission to share this training data with Google Colab.'});
    const prepare=dialog.getByRole('button',{name:'Download notebook',exact:true});
    assert.equal(await consent.isChecked(),false);
    await prepare.click();
    assert.equal(await consent.getAttribute('aria-invalid'),'true');
    await consent.check();
    const [notebook]=await Promise.all([page.waitForEvent('download'),prepare.click()]);
    assert.equal(notebook.suggestedFilename(),'acewyn-colab-training.ipynb');
    const resultBytes=await makeResult(notebook);
    await dialog.waitFor({state:'hidden'});

    await page.reload();
    const openColab=page.getByRole('link',{name:'Open Google Colab',exact:true});
    assert.equal(new URL(await openColab.getAttribute('href')).hostname,'colab.research.google.com');
    await page.getByRole('button',{name:'Download notebook again',exact:true}).waitFor();
    await page.getByRole('button',{name:'Import result',exact:true}).press('Enter');
    const zip=dialog.getByLabel('Result ZIP',{exact:true});
    const importResult=dialog.getByRole('button',{name:'Import and compare',exact:true});
    await zip.setInputFiles({name:'wrong-result.zip',mimeType:'application/zip',buffer:Buffer.from('wrong ZIP')});
    const [invalid]=await Promise.all([
      page.waitForResponse(response=>response.url().endsWith('/result')&&response.request().method()==='POST'),
      importResult.click()
    ]);
    assert.equal(invalid.status(),422);
    await dialog.getByRole('alert').filter({hasText:/could not be verified|result ZIP/i}).waitFor();
    assert.match(await zip.inputValue(),/wrong-result\.zip$/);
    await zip.setInputFiles({name:'acewyn-colab-adapter.zip',mimeType:'application/zip',buffer:resultBytes});
    const [imported]=await Promise.all([
      page.waitForResponse(response=>response.url().endsWith('/result')&&response.request().method()==='POST'),
      importResult.click()
    ]);
    assert(imported.ok(),await imported.text());
    await dialog.waitFor({state:'hidden'});
    await page.getByRole('heading',{name:'Compare Colab answers',exact:true}).waitFor();
    for(const text of [expectedAnswer,'It may take 5–7 working days.','It takes five working days.']){
      await page.getByText(text,{exact:true}).waitFor();
    }
    const looksRight=page.getByRole('button',{name:'Looks right',exact:true});
    await looksRight.click();
    await page.locator('button[aria-pressed="true"]').filter({hasText:'Looks right'}).waitFor();
    await page.reload();
    assert.equal(await looksRight.getAttribute('aria-pressed'),'true');
    if(process.env.OWN_TEST_OUTPUT){
      await page.screenshot({path:path.join(process.env.OWN_TEST_OUTPUT,'colab-training-desktop.png'),fullPage:true});
    }
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Colab review must fit a narrow viewport.');
    if(process.env.OWN_TEST_OUTPUT){
      await page.screenshot({path:path.join(process.env.OWN_TEST_OUTPUT,'colab-training-mobile.png'),fullPage:true});
    }
    await page.getByRole('button',{name:'Download Colab model',exact:true}).click();
    const [model]=await Promise.all([
      page.waitForEvent('download'),
      dialog.getByRole('button',{name:'Download Colab model',exact:true}).click()
    ]);
    assert.equal(model.suggestedFilename(),'acewyn-colab-model.zip');
    assert.equal((await fs.readFile(await model.path())).subarray(0,2).toString(),'PK');
    await dialog.waitFor({state:'hidden'});
    assert.deepEqual(errors,[]);
    assert.deepEqual(external,[]);
    console.log('Colab browser flow passed with a synthetic adapter and zero cloud calls.');
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1});
