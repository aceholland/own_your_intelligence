export function createGpuUI(context) {
  const {state,api,esc,icon,badge,button,field,errorArea,jobShell,jobBase,route,formatDate,
    openModal,closeModal,notify,refreshJob}=context;
  let preparation=null,confirmedPlan=null;
  const chosen=new Map();
  const active=run=>['queued','starting','running','comparing','stopping','interrupted'].includes(run.status);
  const polling=run=>active(run)&&run.status!=='interrupted';
  const link=(url,label)=>`<a class="button secondary" href="${url}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`;
  const billingLink=()=>link('https://modal.com/settings/usage','Open Modal billing');

  function connection(status){
    const installed=status.sdk.status==='ready';
    if(!installed)return `<div class="training-setup spacer"><strong>${esc(status.sdk.phase||'Set up the connection tools once')}</strong>${status.sdk.status==='installing'?'<p class="caption spacer" role="status">Installing local tools… Keep Own open.</p>':`<p class="caption spacer">Install the connection tools on this laptop. This does not start cloud training.</p>${status.sdk.error?`<div class="error-box">${esc(status.sdk.error)}</div>`:''}<button class="button secondary spacer" data-action="gpu-install">Set up GPU tools</button>`}</div>`;
    return `<div class="inline-actions spacer">${badge(status.connected?'Connection saved':'No account connected',status.connected?'good':'')}<button class="button secondary" data-action="gpu-connect-open">${status.connected?'Check another connection':'Connect Modal account'}</button>${status.connected?button('gpu-disconnect','Forget saved connection','','ghost'):''}</div>${status.connection_error?`<div class="error-box">${esc(status.connection_error)}</div>`:''}`;
  }

  function comparison(run){
    const stale=run.dataset_hash!==state.job.gpu_plan.dataset_hash;
    return `<section class="panel"><div class="training-stage"><span class="step-number">3</span><div><h3>See what changed</h3><p class="caption">Real before-and-after answers. You decide whether they look right.</p></div></div>${stale?'<div class="notice warning spacer"><div><strong>Earlier lessons</strong><p>This model belongs to an older draft. Its answers and download keep that original snapshot.</p></div></div>':''}<p class="caption spacer">These checks use the same instructions and requests, with teaching examples and reference files left out of the prompts. Expected answers stayed on your laptop.</p>${run.results.map((row,index)=>`<article class="comparison-case"><div class="panel-header"><h3>Check ${index+1}</h3>${badge(row.error?'Could not finish':row.review==='pass'?'Looks right':row.review==='fail'?'Needs work':'Needs your review',row.review==='pass'?'good':row.error||row.review==='fail'?'warn':'')}</div><p class="request-text">${esc(row.input)}</p><div class="expected-answer"><span class="example-label">What you wanted</span><p>${esc(row.expected)}</p></div><div class="equal-columns spacer"><div class="check-answer"><span class="example-label">Before training</span><p>${esc(row.before||row.before_error||'No complete answer')}</p></div><div class="check-answer trained-answer"><span class="example-label">After training</span><p>${esc(row.after||'No complete answer')}</p></div></div>${row.error?`<div class="error-box">${esc(row.error)} Improve the examples and train again.</div>`:`<div class="review-actions"><span class="caption">The trained answer…</span><button class="button secondary small" data-action="gpu-review" data-run="${run.id}" data-id="${row.check_id}" data-review="fail" aria-pressed="${row.review==='fail'}">Needs work</button><button class="button secondary small" data-action="gpu-review" data-run="${run.id}" data-id="${row.check_id}" data-review="pass" aria-pressed="${row.review==='pass'}">${icon('check',14)}Looks right</button></div>`}</article>`).join('')}<div class="training-decision"><div><strong>Your trained model is yours to keep.</strong><p class="caption">Download it for a supported GPU. Running this larger model inside Own needs GPU hosting, which comes in the next step.</p></div><button class="button secondary" data-action="gpu-export" data-id="${run.id}">${icon('download',16)}Download GPU model</button></div><details class="training-details spacer"><summary>Training details</summary><p class="caption spacer">${esc(run.base.id)} · L4 in the US · ${run.step} actual steps · ${Number(run.changed_parameters||0).toLocaleString()} changed weights</p><p class="caption">Training loss: ${esc(run.first_loss)} → ${esc(run.last_loss)}. This measures fit to teaching answers; it does not measure accuracy.</p><p class="caption">Dataset ${esc(run.dataset_hash.slice(0,12))}. Your review does not change the approved model.</p>${run.app_id?`<p class="caption">Modal app: ${esc(run.app_id)}</p>`:''}</details></section>`;
  }

  function render(){
    const status=state.gpuStatus||{sdk:{status:'not_installed'},connected:false};
    const plan=state.job.gpu_plan,runs=state.job.gpu_runs||[],running=runs.find(active);
    const focused=runs.find(run=>run.id===chosen.get(state.job.id))||runs[0];
    const ready=status.sdk.status==='ready'&&status.connected;
    const busy=state.job.gpu_busy??status.busy;
    return jobShell(`<a class="back-link" href="${route('train',state.job.id)}">${icon('back',15)}Local training</a><div class="training-intro"><div><div class="eyebrow">Your own model · stronger hardware</div><h2>Train a stronger business AI.</h2><p class="lede">Teach it on your laptop. Let a cloud GPU do the heavy work. Review the answers here.</p></div>${badge('Free credits only','good')}</div><div id="gpu-action-error">${errorArea()}</div><div class="training-layout"><div class="stack"><section class="panel"><div class="training-stage"><span class="step-number">1</span><div><h3>Review your lessons</h3><p class="caption">${plan.teaching_count} teaching examples · ${plan.check_count} separate checks</p></div></div><p class="caption spacer">Each business gets its own model update. Start with clear answers and aim for 20 or more varied examples before trusting it.</p>${plan.blockers.length?`<ul class="training-blockers">${plan.blockers.map(item=>`<li>${esc(item)}</li>`).join('')}</ul>`:''}<div class="inline-actions spacer">${button('review-examples','Review examples','book','secondary')}<a class="text-button" href="${route('teach',state.job.id)}">Add examples ${icon('arrow',14)}</a><a class="text-button" href="${route('check',state.job.id)}">Add checks ${icon('arrow',14)}</a></div></section><section class="panel"><div class="training-stage"><span class="step-number">2</span><div><h3>Train with your Modal account</h3><p class="caption">A larger model on one cloud GPU. Keep Own open during the run.</p></div></div>${!ready?connection(status):`<div class="inline-actions spacer">${badge('Connection saved','good')}<span class="caption">Modal runs the training. Own keeps your results.</span></div>`}<div class="notice spacer"><div><strong>Keep this test free</strong><p>In Modal billing, set <strong>Spend limit to $0</strong> so it cannot charge your card. Check that free credits are available.</p><div class="inline-actions spacer">${billingLink()}<button class="text-button" data-action="gpu-billing-help">Explain this simply</button></div><p class="caption spacer">You confirm these settings before each run. Own cannot read or verify them.</p></div></div>${running?`<div class="training-progress spacer" role="status"><strong>${esc(running.phase)}</strong>${running.status==='interrupted'?`<div class="error-box">${esc(running.error)}</div><p class="caption spacer">The cloud stop is unconfirmed. A new run is blocked until it is stopped.</p>`:`<div class="progress-row"><progress value="${running.step}" max="${running.total_steps}" aria-label="Completed GPU training steps"></progress><span class="caption">${running.step} of ${running.total_steps} steps</span></div><p class="caption">The bar counts actual learning steps. Downloading, saving and comparing are separate stages.</p>`}<button class="button secondary spacer" data-action="gpu-cancel" data-id="${running.id}" ${running.status==='stopping'?'disabled':''}>${running.status==='stopping'?'Stopping…':'Stop cloud job'}</button>${running.status==='interrupted'&&running.provider_workspace_name?`<button class="text-button spacer" data-action="gpu-recovery-open" data-id="${running.id}">Reconnect to stop</button>`:''}${running.app_id?`<p class="caption spacer">Cloud app ${esc(running.app_id)}</p>`:''}<div class="spacer">${link('https://modal.com/apps','Open Modal Apps')}</div></div>`:`<div class="inline-actions spacer"><button class="button" data-action="gpu-run-open" ${!ready||!plan.ready||busy?'disabled':''}>${icon('spark',16)}Train on GPU</button><span class="caption">${!ready?'Connect your account to continue.':!plan.ready?'Add the missing examples first.':busy?'A cloud job is still active in another business.':'Review the free-only confirmations before starting.'}</span></div>`}</section>${focused&&!active(focused)&&focused.status!=='complete'?`<div class="notice warning"><div><strong>${focused.status==='cancelled'?'Cloud job stopped':'This training did not finish'}</strong><p>${esc(focused.error||'Your lessons are safe. Review the job details before trying again.')}</p>${focused.app_id?`<p class="caption">Modal app ${esc(focused.app_id)}</p>`:''}</div></div>`:''}${focused?.status==='complete'?comparison(focused):!running?'<section class="panel training-placeholder"><div class="training-stage"><span class="step-number">3</span><div><h3>See what changed</h3><p class="caption">Before-and-after answers appear here after real training and file verification.</p></div></div></section>':''}</div><aside class="stack"><section class="panel mini-note"><div class="job-icon">${icon('shield')}</div><h3 class="spacer">One shared base.<br>Your business’s learning.</h3><p class="caption spacer">Qwen3 4B Instruct · Apache 2.0. Your examples train a separate model update for this job.</p><hr class="rule"><strong>What leaves this laptop?</strong><p class="caption spacer">Teaching examples, instructions and check requests go to Modal in the US. Reference files and expected check answers stay here.</p><p class="caption spacer">Completed results include actual model weights. They need a supported GPU to run. Your laptop’s local AI remains available.</p>${!runs.length?'<p class="caption spacer">The first larger-model GPU test is pending. Model quality will be judged from its real results.</p>':''}</section>${runs.length?`<section class="panel"><h3>GPU training history</h3>${runs.map((run,index)=>`<button class="training-history" data-action="gpu-view" data-id="${run.id}" aria-pressed="${focused?.id===run.id}"><strong>GPU training ${runs.length-index}</strong><span>${esc(formatDate(run.created_at))}</span>${badge(run.status==='complete'?'Ready to review':run.status==='interrupted'?'Stop unconfirmed':run.status==='cancelled'?'Stopped':run.status==='failed'?'Did not finish':'In progress',run.status==='complete'?'good':'')}</button>`).join('')}</section>`:''}<section class="panel"><details><summary>Account and portable setup</summary>${ready?connection(status):`<p class="caption spacer">Create an account if you do not have one yet.</p><div class="spacer">${link('https://modal.com/signup','Create a Modal account')}</div>`}<hr class="rule"><p class="caption">Prepare a private file for running training yourself later. This action stays on your laptop.</p><button class="button secondary full spacer" data-action="gpu-prepare-open" ${!plan.ready?'disabled':''}>Prepare training package</button>${plan.packages.length?`<div class="spacer">${plan.packages.map((item,index)=>`<div class="example"><strong>Package ${plan.packages.length-index}</strong><p class="caption">${esc(formatDate(item.created_at))} · ${item.dataset_hash===plan.dataset_hash?'Current lessons':'Earlier lessons'}</p><button class="text-button" data-action="gpu-download" data-id="${item.id}" ${item.download_available===false?'disabled':''}>${icon('download',16)}Download training package</button></div>`).join('')}</div>`:''}</details></section></aside></div>`);
  }

  function connectionDialog(recoveryRun=null){
    const secret=(name,label,help)=>field(name,label,'',{type:'password',help,max:300})+`<button type="button" class="text-button secret-toggle" data-action="gpu-reveal" data-field="field-${name}" aria-pressed="false" aria-label="Show ${label.toLowerCase()}">Show ${label.toLowerCase()}</button>`;
    openModal(recoveryRun?'Reconnect to stop your cloud job':'Connect your Modal account',`<p>${recoveryRun?'Use a replacement token from the same Modal workspace that owns this job. Own checks its workspace before saving it, then asks Modal to stop the recorded job.':'Create a token pair in your Modal settings, then paste it here. These are connection keys, not your account password.'}</p><p class="spacer">${link('https://modal.com/settings/tokens','Open Modal token settings')}</p><form data-form="${recoveryRun?'gpu-recovery-connect':'gpu-connect'}" ${recoveryRun?`data-run="${recoveryRun}"`:''} novalidate class="spacer">${secret('token_id','Token ID','Usually starts with ak-.')}${secret('token_secret','Token secret','Usually starts with as-. Kept private using Windows protection.')}<p class="caption">${recoveryRun?'This reconnects for stopping only. It cannot launch another training job.':'Checking this pair reads your app list and workspace identity. It does not start compute or upload business examples.'}</p>${errorArea()}<div class="form-actions"><button type="button" class="button secondary" data-action="close-modal">Cancel</button><button class="button" type="submit">${recoveryRun?'Connect and stop cloud job':'Check and save connection'}</button></div></form>`);
  }

  function permission(name,label,help){
    return `<div class="field spacer"><label class="permission-choice" for="gpu-${name}"><input type="checkbox" id="gpu-${name}" name="${name}" required aria-describedby="gpu-${name}-help gpu-${name}-error"><span>${label}</span></label><small id="gpu-${name}-help">${help}</small><div class="form-error" id="gpu-${name}-error"></div></div>`;
  }

  function runDialog(){
    confirmedPlan={...state.job.gpu_plan};
    openModal('Train using free credits',`<p><strong>${esc(state.workspace.name)}</strong> · ${confirmedPlan.teaching_count} teaching examples and ${confirmedPlan.check_count} separate check requests.</p><p class="caption spacer">One L4 in the US, no automatic retry. The 30-minute execution timeout is about $0.59 at requested resources using the 2026-11-02 snapshot, including the US region multiplier. Actual compute, startup, image preparation, storage and network can add usage. This estimate is not a bill limit.</p><form data-form="gpu-run" novalidate>${permission('upload','I have permission to send these lessons to Modal for training in the US.','Includes teaching examples, instructions and check requests. Reference files and expected answers stay local.')}${permission('free_only','Use free credits only. I do not approve any out-of-pocket charges.','There is no paid mode in this training flow.')}${permission('zero_limit','I set Modal’s out-of-pocket Spend limit to $0.','This is the Spend limit after credits, separate from the usage limit. Own cannot verify it.')}${permission('credits','My Modal account has enough free credits for this test.','Check the current credit balance in Modal billing. Own cannot verify it.')}<p class="caption">${billingLink()}</p>${errorArea()}<div class="form-actions"><button type="button" class="button secondary" data-action="close-modal">Cancel</button><button class="button" type="submit">Start with free credits</button></div></form>`);
  }

  function preparationDialog(){
    preparation={...state.job.gpu_plan};
    openModal('Prepare your GPU training package',`<p><strong>${esc(state.workspace.name)}</strong> · ${preparation.teaching_count} teaching examples and ${preparation.check_count} separate check requests.</p><p class="caption spacer">This makes a private local ZIP. It does not start training or upload business information.</p><form data-form="gpu-prepare" novalidate class="spacer">${field('budget_usd','Planning allowance (USD)','2.00',{type:'number',help:'$0.50–$25. A planning value, not permission to spend or a hard bill limit.'})}<p class="caption">The preset requests one L4 in the US with a 30-minute execution timeout, about $0.59 at requested resources using the 2026-11-02 rate snapshot and region multiplier. Actual compute can vary; startup, preparation, storage, network and taxes can add charges. Set a provider Spend limit before launching.</p>${permission('permission','I have permission to prepare these business examples in a private local file.','No cloud run or upload is approved by this action.')}${errorArea()}<div class="form-actions"><button type="button" class="button secondary" data-action="close-modal">Cancel</button><button class="button" type="submit">Prepare private package</button></div></form>`);
  }

  async function submit(type,form,data,path,stillHere){
    if(type==='gpu-recovery-connect'){
      await api(`${path}/gpu/runs/${form.dataset.run}/reconnect`,{method:'POST',body:data,timeout:65000});
      if(stillHere()){closeModal();await refreshJob();context.poll();notify('Recovery connection checked. Confirming the cloud stop.');}
      return true;
    }
    if(type==='gpu-connect'){
      const response=await api('/api/gpu/connection',{method:'POST',body:data,timeout:65000});
      state.gpuStatus=response;
      if(stillHere()){closeModal();await refreshJob();notify('Connection saved. No training was started.');}
      return true;
    }
    if(type==='gpu-prepare'){
      if(data.permission!=='on')throw new Error('Confirm permission to prepare this private file.');
      await api(`${path}/gpu/packages`,{method:'POST',body:{dataset_hash:preparation.dataset_hash,budget_usd:Number(data.budget_usd),permission:true}});
      if(stillHere()){closeModal();await refreshJob();notify('Private package prepared. Nothing has been uploaded or trained.');}
      return true;
    }
    if(type==='gpu-run'){
      const approvals={};
      for(const key of ['upload','free_only','zero_limit','credits']){
        if(data[key]!=='on')throw new Error('Confirm all four permissions and free-only settings before training.');
        approvals[key]=true;
      }
      await api(`${path}/gpu/runs`,{method:'POST',body:{dataset_hash:confirmedPlan.dataset_hash,...approvals}});
      if(stillHere()){chosen.delete(state.job.id);closeModal();await refreshJob();context.poll();notify('GPU job started with your free-only confirmations.');}
      return true;
    }
    return false;
  }

  async function handle(action,target){
    if(action==='gpu-recovery-open'){connectionDialog(target.dataset.id);return true;}
    if(action==='gpu-connect-open'){connectionDialog();return true;}
    if(action==='gpu-prepare-open'){preparationDialog();return true;}
    if(action==='gpu-run-open'){runDialog();return true;}
    if(action==='gpu-billing-help'){
      openModal('Keep this test free',`<p>Free credits are like a prepaid balance. We want Modal to use that balance and charge your card <strong>$0</strong>.</p><ol class="spacer"><li>Open Modal billing using the button below.</li><li>Find <strong>Spend limit</strong>, set it to <strong>0</strong>, and save.</li><li>Check that your account has free credits remaining.</li></ol><p class="caption spacer">Spend limit controls what you pay after credits. Setting the separate usage limit to $0 can stop free training too. If you cannot find Spend limit, leave training unstarted.</p><div class="inline-actions spacer">${billingLink()}${link('https://modal.com/docs/guide/budgets','Modal’s instructions')}</div><div class="form-actions"><button class="button secondary" data-action="close-modal">Back to Own</button></div>`);return true;
    }
    if(action==='gpu-reveal'){
      const input=document.getElementById(target.dataset.field),show=input.type==='password';
      input.type=show?'text':'password';target.setAttribute('aria-pressed',String(show));
      const label=input.labels[0].textContent.toLowerCase();target.textContent=`${show?'Hide':'Show'} ${label}`;target.setAttribute('aria-label',target.textContent);return true;
    }
    if(action==='gpu-view'){chosen.set(state.job.id,target.dataset.id);await refreshJob();return true;}
    if(!['gpu-install','gpu-disconnect','gpu-download','gpu-cancel','gpu-review','gpu-export'].includes(action))return false;
    const serial=state.serial,path=state.job?jobBase():null;
    target.disabled=true;
    try{
      if(action==='gpu-install')state.gpuStatus=await api('/api/gpu/setup',{method:'POST',body:{}});
      else if(action==='gpu-disconnect')state.gpuStatus=await api('/api/gpu/disconnect',{method:'POST',body:{}});
      else if(action==='gpu-cancel')await api(`${path}/gpu/runs/${target.dataset.id}/cancel`,{method:'POST',body:{}});
      else if(action==='gpu-review')await api(`${path}/gpu/runs/${target.dataset.run}/review`,{method:'POST',body:{check_id:target.dataset.id,review:target.dataset.review}});
      else if(action==='gpu-export'){
        const id=target.dataset.id;
        context.confirmAction('Download your GPU model?','This private ZIP includes real model-update weights, teaching examples, checks, reviews and a standalone CUDA runner. Public base weights are downloaded separately. Running it requires a supported GPU.','Download private model',async()=>{
          await context.download(`${path}/gpu/runs/${id}/export`,'own-gpu-trained-model.zip');closeModal();notify('GPU model downloaded. Keep it private.');
        });return true;
      }else {await context.download(`${path}/gpu/packages/${target.dataset.id}/export`,'own-gpu-training-setup.zip');notify('Private GPU package downloaded. No training has started.');return true;}
      if(serial===state.serial){await refreshJob();if(action==='gpu-cancel'||state.gpuStatus.sdk.status==='installing')context.poll();}
      return true;
    }finally{if(target.isConnected)target.disabled=false;}
  }
  return {render,submit,handle,active,polling};
}
