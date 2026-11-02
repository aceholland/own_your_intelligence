const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const origin=process.env.OWN_TEST_URL||'http://127.0.0.1:8765';
const jobRoute=process.env.OWN_TEST_JOB||'#w/dff830bc6e34461ab7d009b10a9cec53/j/ae0d277606b247188e5b4732f9411e71/train';
const output=process.env.OWN_TEST_OUTPUT||process.cwd();

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900},acceptDownloads:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(origin+'/'+jobRoute);
    await page.getByRole('link',{name:'Set up a stronger model',exact:true}).click();
    await page.getByRole('heading',{name:'Give your AI more room to learn.',exact:true}).waitFor();
    await page.getByRole('button',{name:'Connect Modal account',exact:true}).click();
    await page.getByLabel('Token ID',{exact:true}).fill('invalid-format-id');
    await page.getByLabel('Token secret',{exact:true}).fill('invalid-format-secret');
    assert.equal(await page.getByLabel('Token secret',{exact:true}).getAttribute('type'),'password');
    await page.getByRole('button',{name:'Show token secret',exact:true}).click();
    assert.equal(await page.getByLabel('Token secret',{exact:true}).getAttribute('type'),'text');
    await page.getByRole('button',{name:'Hide token secret',exact:true}).click();
    await page.getByRole('button',{name:'Check and save connection',exact:true}).click();
    await page.getByRole('dialog').getByText('Copy the token ID and secret from your Modal account. Do not use your account password.',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('Token secret',{exact:true}).inputValue(),'invalid-format-secret');
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Prepare training package',exact:true}).click();
    await page.getByRole('button',{name:'Prepare private package',exact:true}).click();
    assert.equal(await page.locator('#gpu-permission').getAttribute('aria-invalid'),'true');
    await page.getByLabel('I have permission to prepare these business examples in a private local file.').check();
    await page.getByLabel('Planning allowance (USD)',{exact:true}).fill('0.10');
    await page.getByRole('button',{name:'Prepare private package',exact:true}).click();
    await page.getByRole('dialog').getByText('Choose a planning allowance from $0.50 to $25 USD.',{exact:true}).waitFor();
    await page.getByLabel('Planning allowance (USD)',{exact:true}).fill('2.00');
    await page.getByRole('button',{name:'Prepare private package',exact:true}).click();
    await page.locator('#dialog').waitFor({state:'hidden'});
    const download=page.waitForEvent('download');
    await page.getByRole('button',{name:'Download training package',exact:true}).first().click();
    await (await download).saveAs(path.join(output,'step3-gpu-setup.zip'));
    await page.locator('#toast').waitFor({state:'hidden',timeout:10000});
    await page.screenshot({path:path.join(output,'step3-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    const size=await page.evaluate(()=>({innerWidth,documentWidth:document.documentElement.scrollWidth}));
    assert(size.documentWidth<=size.innerWidth);
    await page.screenshot({path:path.join(output,'step3-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({prepared:true,downloaded:true,credentialMaskReveal:true,noCloudRun:true,size,errors}));
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
