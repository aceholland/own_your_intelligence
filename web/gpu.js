export function createGpuUI(context) {
  const {state,api,esc,icon,badge,button,field,errorArea,jobShell,jobBase,route,formatDate,
    openModal,closeModal,notify,refreshJob}=context;
  let preparation=null;
  const link=(url,label)=>`<a class="button secondary" href="${url}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`;

  function render(){
    const status=state.gpuStatus||{sdk:{status:'not_installed',phase:'Load connection tools'},connected:false};
    const plan=state.job.gpu_plan;
    const installed=status.sdk.status==='ready';
    return jobShell(`<a class="back-link" href="${route('train',state.job.id)}">${icon('back',15)}Local training</a><div class="training-intro"><div><div class="eyebrow">Stronger models · setup first</div><h2>Give your AI more room to learn.</h2><p class="lede">Prepare for a larger model on a rented GPU. Your laptop stays the place where you teach and review.</p></div>${badge('No cloud run started','good')}</div><div id="gpu-action-error">${errorArea()}</div><div class="two-column"><div class="stack"><section class="panel"><div class="training-stage"><span class="step-number">1</span><div><h3>Create your GPU account</h3><p class="caption">Modal runs the larger model in your own cloud account.</p></div></div><p class="caption spacer">You create the account on Modal’s website. Own will not sign up or add billing details for you.</p><div class="inline-actions spacer">${link('https://modal.com/signup','Create a Modal account')}${link('https://modal.com/pricing','View current pricing')}</div></section><section class="panel"><div class="training-stage"><span class="step-number">2</span><div><h3>Set your spending limit</h3><p class="caption">Use Modal’s billing controls before any paid run.</p></div></div><p class="caption spacer">A planning allowance helps size a job. The provider’s spending limit controls your bill. Preparing files or checking a connection does not start training.</p><div class="spacer">${link('https://modal.com/docs/guide/budgets','How to set a spending limit')}</div></section><section class="panel"><div class="training-stage"><span class="step-number">3</span><div><h3>Connect your account</h3><p class="caption">A read-only check. No app deployment, training or business-data upload.</p></div></div>${status.connection_error?`<div class="error-box">${esc(status.connection_error)}</div>`:''}${!installed?`<div class="training-setup spacer"><strong>${esc(status.sdk.phase)}</strong>${status.sdk.status==='installing'?'<p class="caption spacer" role="status">Installing local tools… You can leave this tab. Keep Own open.</p>':`<p class="caption spacer">Install the small connection tools on this laptop once. This does not create cloud resources.</p>${status.sdk.error?`<div class="error-box">${esc(status.sdk.error)}</div>`:''}<button class="button secondary spacer" data-action="gpu-install">Set up GPU tools</button>`}</div>`:`<div class="inline-actions spacer">${badge(status.connected?'Connection saved':'No account connected',status.connected?'good':'')}<button class="button secondary" data-action="gpu-connect-open">${status.connected?'Check another connection':'Connect Modal account'}</button>${status.connected?button('gpu-disconnect','Forget saved connection','','ghost'):''}</div><p class="caption spacer">${esc(status.credential_storage)}. Secret values never appear in exports or browser storage.</p>`}</section></div><aside class="stack"><section class="panel"><div class="panel-header"><h3>Prepare your business’s lessons</h3>${icon('book',18)}</div><p class="caption">You can do this before creating an account. A private package freezes your reviewed examples and instructions.</p><p class="spacer"><strong>${plan.teaching_count} teaching examples</strong><br><span class="caption">${plan.check_count} separate checks · Qwen3 4B Instruct</span></p>${plan.blockers.length?`<ul class="training-blockers">${plan.blockers.map(item=>`<li>${esc(item)}</li>`).join('')}</ul>`:''}<button class="button full spacer" data-action="gpu-prepare-open" ${!plan.ready?'disabled':''}>Prepare training package ${icon('arrow',16)}</button><p class="caption spacer">This saves a file on your laptop. It does not upload data, train a model or authorize spending.</p><hr class="rule"><p class="caption">Future upload includes teaching examples, instructions and check requests. Your reference files and expected check answers stay local.</p></section><div class="notice">${icon('info')}<div><strong>The next run needs your approval.</strong><p>After your account is ready, we’ll verify a real GPU run before enabling larger models in Own. Local training is available now.</p></div></div>${plan.packages.length?`<section class="panel"><h3>Prepared packages</h3>${plan.packages.map((p,i)=>`<div class="example"><strong>Package ${plan.packages.length-i}</strong><p class="caption">${esc(formatDate(p.created_at))} · ${p.dataset_hash===plan.dataset_hash?'Current lessons':'Earlier lessons'}</p><p class="caption">${p.download_available===false?'Prepare a fresh package to include its frozen trainer.':'Private file · not uploaded or trained'}</p><button class="text-button" data-action="gpu-download" data-id="${p.id}" ${p.download_available===false?'disabled':''}>${icon('download',16)}Download training package</button></div>`).join('')}</section>`:''}</aside></div>`);
  }

  function connectionDialog(){
    const secret=(name,label,help)=>field(name,label,'',{type:'password',help,max:300})+`<button type="button" class="text-button secret-toggle" data-action="gpu-reveal" data-field="field-${name}" aria-pressed="false" aria-label="Show ${label.toLowerCase()}">Show ${label.toLowerCase()}</button>`;
    openModal('Connect your Modal account',`<p>Create a token pair in your Modal settings, then paste it here. These are connection keys, not your account password.</p><p class="spacer">${link('https://modal.com/settings/tokens','Open Modal token settings')}</p><form data-form="gpu-connect" novalidate class="spacer">${secret('token_id','Token ID','Usually starts with ak-.')}${secret('token_secret','Token secret','Usually starts with as-. Kept private using Windows protection.')}<p class="caption">Checking this pair only reads your app list. It does not start compute or upload your business examples.</p>${errorArea()}<div class="form-actions"><button type="button" class="button secondary" data-action="close-modal">Cancel</button><button class="button" type="submit">Check and save connection</button></div></form>`);
  }

  function preparationDialog(){
    preparation={...state.job.gpu_plan};
    openModal('Prepare your GPU training package',`<p><strong>${esc(state.workspace.name)}</strong> · ${preparation.teaching_count} teaching examples and ${preparation.check_count} separate check requests.</p><p class="caption spacer">This makes a private local ZIP. It does not connect to a provider or start training.</p><form data-form="gpu-prepare" novalidate class="spacer">${field('budget_usd','Planning allowance (USD)','2.00',{type:'number',help:'$0.50–$25. A planning value, not permission to spend or a hard bill limit.'})}<p class="caption">The preset allows at most 30 minutes on one L4. Current compute estimate is up to about $0.51, excluding image preparation, storage, network and taxes. Set a provider spending limit before launching.</p><div class="field spacer"><label class="permission-choice" for="gpu-permission"><input type="checkbox" id="gpu-permission" name="permission" required aria-describedby="gpu-permission-help gpu-permission-error"><span>I have permission to prepare these business examples in a private local file.</span></label><small id="gpu-permission-help">No cloud run or upload is approved by this action.</small><div class="form-error" id="gpu-permission-error"></div></div>${errorArea()}<div class="form-actions"><button type="button" class="button secondary" data-action="close-modal">Cancel</button><button class="button" type="submit">Prepare private package</button></div></form>`);
  }

  async function submit(type,form,data,path,stillHere){
    if(type==='gpu-connect'){
      const response=await api('/api/gpu/connection',{method:'POST',body:data,timeout:40000});
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
    return false;
  }

  async function handle(action,target){
    if(action==='gpu-connect-open'){connectionDialog();return true;}
    if(action==='gpu-prepare-open'){preparationDialog();return true;}
    if(action==='gpu-reveal'){
      const input=document.getElementById(target.dataset.field),show=input.type==='password';
      input.type=show?'text':'password';target.setAttribute('aria-pressed',String(show));
      const label=input.labels[0].textContent.toLowerCase();target.textContent=`${show?'Hide':'Show'} ${label}`;target.setAttribute('aria-label',target.textContent);return true;
    }
    if(!['gpu-install','gpu-disconnect','gpu-download'].includes(action))return false;
    const serial=state.serial,path=state.job?jobBase():null;
    target.disabled=true;
    try{
      if(action==='gpu-install')state.gpuStatus=await api('/api/gpu/setup',{method:'POST',body:{}});
      else if(action==='gpu-disconnect')state.gpuStatus=await api('/api/gpu/disconnect',{method:'POST',body:{}});
      else {await context.download(`${path}/gpu/packages/${target.dataset.id}/export`,'own-gpu-training-setup.zip');notify('Private GPU package downloaded. No training has started.');return true;}
      if(serial===state.serial){await refreshJob();if(state.gpuStatus.sdk.status==='installing')context.poll();}
      return true;
    }finally{if(target.isConnected)target.disabled=false;}
  }
  return {render,submit,handle};
}
