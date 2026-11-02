// Training follows the app's existing modal, form, notification and API owners.
export function createTrainingUI(context) {
  const {state, api, esc, icon, badge, button, field, errorArea, formatDate,
    jobShell, jobBase, route, openModal, closeModal, notify, refreshJob} = context;
  const active = run => ['queued','running','comparing','cancelling'].includes(run?.status);
  const chosen = new Map();
  let editing = null;
  let confirmedPlan = null;

  function reviewExamples() {
    const examples = state.job.examples;
    openModal('Review your examples', `<p>Train on answers you would be happy to send. Checks stay separate and never teach the model.</p>${examples.length ? examples.map(e=>`<div class="example"><div class="panel-header"><strong>${e.kind==='teach'?'Teaching example':'Separate check'}</strong><button class="button secondary small" data-action="edit-example" data-id="${e.id}">Edit</button></div><p>${esc(e.input)}</p><p class="caption">${esc(e.output)}</p></div>`).join('') : '<p class="caption spacer">No examples yet. Add them in Teach it and Check it.</p>'}<div class="form-actions"><button class="button secondary" data-action="close-modal">Done reviewing</button></div>`);
  }

  function editExample(id) {
    editing = state.job.examples.find(e=>e.id===id);
    if (!editing) throw new Error('This example is no longer available. Refresh the page.');
    openModal(editing.kind==='teach'?'Edit teaching example':'Edit separate check', `<p>Saved training and approved versions keep their original examples. This changes your draft.</p><form data-form="edit-example" novalidate>${field('input','Someone asks…',editing.input,{type:'textarea',short:true})}${field('output',editing.kind==='teach'?'A good answer':'What should a good answer include?',editing.output,{type:'textarea',max:6000})}${errorArea()}<div class="form-actions"><button class="button secondary" type="button" data-action="close-modal">Cancel</button><button class="button" type="submit">Save example</button></div></form>`);
  }

  function trainDialog() {
    confirmedPlan = {...state.job.training_plan};
    const plan = confirmedPlan;
    openModal('Train your business AI', `<div class="notice">${icon('shield')}<div><strong>${esc(state.workspace.name)} · ${plan.teaching_count} teaching examples</strong><p>${plan.check_count} separate check${plan.check_count===1?'':'s'} will compare the results. Your current approved AI stays in place.</p></div></div><p class="spacer">Training runs on this laptop using the small starter model. <strong>No provider charge.</strong> No business examples are uploaded.</p><p class="caption spacer">Keep Own open. Training can take several minutes or longer, depending on your examples. A small training does not guarantee better answers.</p><form data-form="train-confirm" novalidate><div class="field spacer"><label class="permission-choice" for="train-permission"><input id="train-permission" type="checkbox" name="permission" required aria-describedby="train-permission-help train-permission-error"><span>I have permission to use these business examples for local model training.</span></label><small id="train-permission-help">Only the examples you reviewed are used for teaching.</small><div class="form-error" id="train-permission-error"></div></div>${errorArea()}<div class="form-actions"><button class="button secondary" type="button" data-action="close-modal" data-initial-focus>Cancel</button><button class="button" type="submit">Train my AI ${icon('spark',16)}</button></div></form>`);
  }

  function comparison(run) {
    const stale = run.dataset_hash !== state.job.training_plan.dataset_hash;
    const allRight = run.results.length > 0 && run.results.every(r=>r.review==='pass'&&!r.error);
    const selected = state.job.model === `own:${run.id}`;
    return `<section class="panel"><div class="panel-header"><div><h2>Did training help?</h2><p class="caption">${esc(formatDate(run.created_at))}</p></div>${badge(stale?'Examples have changed':selected?'Selected for your draft':'Ready for review',stale?'warn':selected?'good':'')}</div><p>Compare each answer with what you wanted. Mark the trained answers that look right.</p><p class="caption spacer">Both use the same small base model, instructions and request. Teaching examples and reference notes are left out of this comparison. This tests the saved training itself. If the original model could not finish, its failure is shown; you can still judge the trained answer.</p>${stale?'<div class="notice warning spacer"><div><strong>This belongs to an older draft.</strong><p>You can inspect and download it. Train a fresh update before selecting it for your current draft.</p></div></div>':''}${run.results.map((row,i)=>`<article class="comparison-case"><div class="panel-header"><h3>Check ${i+1}</h3>${badge(row.error?'Could not finish':row.review==='pass'?'Looks right':row.review==='fail'?'Needs work':'Needs your review',row.review==='pass'?'good':row.error||row.review==='fail'?'warn':'')}</div><p class="request-text">${esc(row.input)}</p><div class="expected-answer"><span class="example-label">What you wanted</span><p>${esc(row.expected)}</p></div><div class="equal-columns spacer"><div class="check-answer"><span class="example-label">Before training</span><p>${esc(row.before||row.before_error||'No complete answer')}</p></div><div class="check-answer trained-answer"><span class="example-label">After training</span><p>${esc(row.after||'No complete answer')}</p></div></div>${row.error?`<div class="error-box">${esc(row.error)} Improve the examples and start a new training.</div>`:`<div class="review-actions"><span class="caption">The trained answer…</span><button class="button secondary small" data-action="training-review" data-training="${run.id}" data-id="${row.check_id}" data-review="fail" aria-pressed="${row.review==='fail'}">Needs work</button><button class="button secondary small" data-action="training-review" data-training="${run.id}" data-id="${row.check_id}" data-review="pass" aria-pressed="${row.review==='pass'}">${icon('check',14)}Looks right</button></div>`}</article>`).join('')}<div class="training-decision"><div><strong>${selected?'This training is selected for your draft.':'You decide when to use it.'}</strong><p class="caption">${selected?'Try it, then run Check it and approve a version before live use.':'Only select it when every trained answer looks right. More varied checks give stronger evidence.'}</p></div>${selected?`<a class="button" href="${route('try',state.job.id)}">Try my trained AI ${icon('arrow',16)}</a>`:`<button class="button" data-action="training-select" data-id="${run.id}" ${!allRight||stale?'disabled':''}>Use this training ${icon('arrow',16)}</button>`}</div><div class="inline-actions spacer"><button class="text-button" data-action="training-export" data-id="${run.id}">${icon('download',16)}Download trained model</button><span class="caption">Includes your private training data and adapter. Public base downloaded separately.</span></div><details class="training-details spacer"><summary>Training details</summary><p class="caption spacer">${esc(run.base.id)} · CPU LoRA · ${run.step} actual steps · ${Number(run.changed_parameters||0).toLocaleString()} changed weights</p><p class="caption">Training loss: ${esc(run.first_loss)} → ${esc(run.last_loss)}. This measures fit to teaching answers, not accuracy or business quality.</p><p class="caption">Dataset ${esc(run.dataset_hash.slice(0,12))} · frozen when you confirmed permission.</p></details></section>`;
  }

  function render() {
    const j = state.job, plan = j.training_plan, runtime = state.trainingRuntime || {status:'not_installed'};
    const runs = j.trainings || [];
    const running = runs.find(active);
    const focused = runs.find(r=>r.id===chosen.get(j.id)) || runs[0];
    const ready = runtime.status === 'ready';
    return jobShell(`<div class="training-intro"><div><div class="eyebrow">Your examples become a model update</div><h2>Make it learn your way.</h2><p class="lede">Review the lessons, train your AI, then see whether its answers improve.</p><a class="text-button spacer" href="${route('gpu',j.id)}">Set up a stronger model ${icon('arrow',14)}</a></div>${badge('On this laptop · no provider charge','good')}</div><div id="training-action-error">${errorArea()}</div><div class="training-layout"><div class="stack"><section class="panel"><div class="training-stage"><span class="step-number">1</span><div><h3>Review what it will learn</h3><p class="caption">${plan.teaching_count} teaching examples · ${plan.check_count} separate checks</p></div></div><p class="caption spacer">Use clear, correct answers. Start with a few examples to try training; aim for 20 or more varied examples and several checks before trusting an update.</p>${plan.blockers.length?`<ul class="training-blockers">${plan.blockers.map(b=>`<li>${esc(b)}</li>`).join('')}</ul>`:''}<div class="inline-actions spacer">${button('review-examples','Review examples','book','secondary')}<a class="text-button" href="${route('teach',j.id)}">Add teaching examples ${icon('arrow',14)}</a><a class="text-button" href="${route('check',j.id)}">Add checks ${icon('arrow',14)}</a></div></section><section class="panel"><div class="training-stage"><span class="step-number">2</span><div><h3>Train your business AI</h3><p class="caption">A separate model update for this job and business.</p></div></div>${!ready?`<div class="training-setup spacer"><strong>${esc(runtime.phase)}</strong>${runtime.status==='installing'?'<div class="loading-answer"><span class="spinner" aria-hidden="true"></span><span role="status">Setting up… You can leave this tab. Keep Own running.</span></div>':`<p class="caption spacer">One-time setup installs the CPU tools and downloads the public starter model, about 270 MB plus dependencies. Allow about 2 GB of disk space and an internet connection. Your examples stay here.</p>${runtime.error?`<div class="error-box">${esc(runtime.error)}</div>`:''}<button class="button secondary spacer" data-action="setup-training">Set up local training ${icon('download',16)}</button>`}</div>`:running?`<div class="training-progress spacer" role="status"><strong>${esc(running.phase)}</strong><div class="progress-row"><progress value="${running.step}" max="${running.total_steps}" aria-label="Completed training steps"></progress><span class="caption">${running.step} of ${running.total_steps} steps</span></div><p class="caption">Your approved version is kept. Keep Own open; you can use other tabs.</p><button class="button secondary spacer" data-action="cancel-training" data-id="${running.id}" ${running.status==='cancelling'?'disabled':''}>${running.status==='cancelling'?'Stopping…':'Stop training'}</button></div>`:`<div class="inline-actions spacer"><button class="button" data-action="start-training" ${!plan.ready||runtime.busy?'disabled':''}>${icon('spark',16)}Train my AI</button><span class="caption">${runtime.busy?'Your laptop is already training another job.':plan.ready?'Your examples are ready to review and train.':'Add the missing examples first.'}</span></div>`}</section>${focused&&!active(focused)&&focused.status!=='complete'?`<div class="notice warning"><div><strong>${focused.status==='cancelled'?'Training stopped':'This training did not finish'}</strong><p>${esc(focused.error||'Your examples are safe. Start a new training when you are ready.')}</p></div></div>`:''}${focused?.status==='complete'?comparison(focused):!running?'<div class="panel training-placeholder"><div class="training-stage"><span class="step-number">3</span><div><h3>Compare before you use it</h3><p class="caption">Real before-and-after answers appear here when training finishes. You make the final call.</p></div></div></div>':''}</div><aside class="stack"><section class="panel mini-note"><div class="job-icon">${icon('shield')}</div><h3 class="spacer">One shared base.<br>Your own training.</h3><p class="spacer">Each business starts with the same model. Its teaching examples and saved model updates stay separate.</p><hr class="rule"><strong>A small local starter</strong><p class="caption spacer">SmolLM2 · 135M · English. It makes real training possible on this laptop, with limited answer quality. Stronger models need more capable hardware.</p><p class="caption spacer">Reference files help with answers in Try it. Training learns only from your reviewed teaching examples.</p></section>${runs.length?`<section class="panel"><h3>Training history</h3>${runs.map((run,i)=>`<button class="training-history" data-action="view-training" data-id="${run.id}" aria-pressed="${focused?.id===run.id}"><strong>Training ${runs.length-i}</strong><span>${esc(formatDate(run.created_at))}</span>${badge(run.status==='complete'?'Ready to review':run.status==='failed'?'Did not finish':run.status==='interrupted'?'Interrupted':run.status==='cancelled'?'Stopped':'In progress',run.status==='complete'?'good':'')}</button>`).join('')}</section>`:''}</aside></div>`);
  }

  async function submit(type, form, data, jobPath, stillHere) {
    if (type === 'edit-example') {
      const expected = editing;
      await api(`${jobPath}/examples/${expected.id}`, {method:'PATCH',body:{...data,expected}});
      if (stillHere()) {closeModal();await refreshJob();notify('Example saved. Earlier training keeps its original data.');}
      return true;
    }
    if (type === 'train-confirm') {
      if (data.permission !== 'on') throw new Error('Confirm you have permission to train on these examples.');
      await api(`${jobPath}/train`, {method:'POST',body:{dataset_hash:confirmedPlan.dataset_hash,permission:true}});
      if (stillHere()) {chosen.delete(state.job.id);closeModal();await refreshJob();context.poll();notify('Training started on this laptop.');}
      return true;
    }
    return false;
  }

  async function handle(action, target) {
    const serial=state.serial, path=state.job?jobBase():null;
    const here=()=>serial===state.serial;
    if(action==='review-examples'){reviewExamples();return true;}
    if(action==='edit-example'){editExample(target.dataset.id);return true;}
    if(action==='start-training'){trainDialog();return true;}
    if(action==='view-training'){chosen.set(state.job.id,target.dataset.id);await refreshJob();return true;}
    if(!['setup-training','cancel-training','training-review','training-select','training-export'].includes(action))return false;
    target.disabled=true;
    try {
      if(action==='setup-training'){
        state.trainingRuntime=await api('/api/training/setup',{method:'POST',body:{}});
        if(here()){await refreshJob();context.poll();notify('Setting up local training. Your business examples stay here.');}
      } else if(action==='cancel-training'){
        await api(`${path}/trainings/${target.dataset.id}/cancel`,{method:'POST',body:{}});
        if(here()){await refreshJob();context.poll();notify('Training is stopping. Your examples are safe.');}
      } else if(action==='training-review'){
        await api(`${path}/trainings/${target.dataset.training}/review`,{method:'POST',body:{check_id:target.dataset.id,review:target.dataset.review}});
        if(here()){await refreshJob();notify('Your review is saved.');}
      } else if(action==='training-select'){
        await api(`${path}/trainings/${target.dataset.id}/select`,{method:'POST',body:{}});
        if(here()){await refreshJob();notify('Training selected for your draft. Try it, then check and approve a version.');}
      } else {
        const id=target.dataset.id;
        context.confirmAction('Download your trained model?','This ZIP includes the real business-specific adapter, your teaching data, separate checks and a standalone runner. Keep it private. The exact public base model is downloaded separately by the runner.','Download trained model',async()=>{
          await context.download(`${path}/trainings/${id}/export`,'own-trained-model.zip');closeModal();notify('Trained model downloaded. Keep it private.');
        });
      }
      return true;
    } finally {if(target.isConnected)target.disabled=false;}
  }

  return {render, submit, handle, active};
}
