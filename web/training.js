// Training follows the app's existing modal, form, notification and API owners.
export function createTrainingUI(context) {
  const {state, api, esc, icon, badge, button, field, errorArea, formatDate,
    jobShell, jobBase, route, openModal, closeModal, notify, refreshJob} = context;
  const active = run => ['queued','running','comparing','cancelling'].includes(run?.status);
  const chosen = new Map();
  const chosenColab = new Map();
  const notebookName = 'acewyn-colab-training.ipynb';
  const resultName = 'acewyn-colab-adapter.zip';
  const resultLimit = 64 * 1024 * 1024;
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

  function prepareColabDialog() {
    const plan = state.job.training_plan;
    const lessons = `${plan.teaching_count} teaching example${plan.teaching_count===1?'':'s'}`;
    const checks = `${plan.check_count} check question${plan.check_count===1?'':'s'}`;
    openModal('Prepare your Colab notebook', `
      <p>This notebook contains your instructions, ${lessons}, and ${checks}. Your expected answers and reference files stay on this laptop.</p>
      <p>You'll download the notebook here, then upload it to Google Colab. Keep the file private.</p>
      <form data-form="colab-prepare" data-dataset="${esc(plan.dataset_hash)}" novalidate>
        <div class="field">
          <label class="permission-choice" for="colab-permission">
            <input id="colab-permission" type="checkbox" name="permission" required aria-describedby="colab-permission-error">
            <span>I have permission to share this training data with Google Colab.</span>
          </label>
          <div class="form-error" id="colab-permission-error"></div>
        </div>
        ${errorArea()}
        <div class="form-actions">
          <button class="button secondary" type="button" data-action="close-modal">Cancel</button>
          <button class="button" type="submit">Download notebook ${icon('download',16)}</button>
        </div>
      </form>`);
  }

  function importColabDialog(runId) {
    openModal('Import your Colab result', `
      <p>Choose the ZIP downloaded from the last cell of this run's Colab notebook. We'll check the file here and show the before and after answers.</p>
      <form data-form="colab-import" data-run="${esc(runId)}" novalidate>
        <div class="field">
          <label for="colab-result">Result ZIP</label>
          <input id="colab-result" type="file" name="result" accept=".zip,application/zip" required aria-describedby="colab-result-help colab-result-error">
          <small id="colab-result-help">${resultName} · up to 64 MB</small>
          <div class="form-error" id="colab-result-error"></div>
        </div>
        ${errorArea()}
        <div class="form-actions">
          <button class="button secondary" type="button" data-action="close-modal">Cancel</button>
          <button class="button" type="submit">Import and compare ${icon('arrow',16)}</button>
        </div>
      </form>`);
  }

  function colabSteps(run, stale) {
    return `
      ${stale?'<p class="caption spacer">This notebook uses earlier examples. You can still import its result for review.</p>':''}
      <ol class="colab-steps spacer" aria-label="Finish training in Colab">
        <li class="roadmap-row">
          <span class="step-number" aria-hidden="true">1</span>
          <div class="roadmap-copy">
            <strong>Your notebook is ready</strong>
            <p>Find <b>${notebookName}</b> in your downloads.</p>
            <button class="text-button" data-action="colab-notebook" data-id="${esc(run.id)}">Download notebook again</button>
          </div>
        </li>
        <li class="roadmap-row">
          <span class="step-number" aria-hidden="true">2</span>
          <div class="roadmap-copy">
            <strong>Run it in Google Colab</strong>
            <p>Upload the notebook. Choose <b>Runtime → Change runtime type → T4 GPU</b>, then <b>Runtime → Run all</b>. Stay on the free plan. If Colab asks you to upgrade, try again later.</p>
            <a class="button secondary small spacer" href="https://colab.research.google.com/" target="_blank" rel="noopener noreferrer">Open Google Colab ${icon('arrow',14)}</a>
          </div>
        </li>
        <li class="roadmap-row">
          <span class="step-number" aria-hidden="true">3</span>
          <div class="roadmap-copy">
            <strong>Bring your result back</strong>
            <p>Download ${resultName} from Colab, then import it here.</p>
            <button class="button small spacer" data-action="colab-import" data-id="${esc(run.id)}">${icon('upload',16)}Import result</button>
          </div>
        </li>
      </ol>`;
  }

  function colabTraining() {
    const job = state.job;
    const plan = job.training_plan;
    const runs = job.colab_runs || [];
    const run = runs.find(item=>item.id===chosenColab.get(job.id)) || runs[0];
    const stale = run && run.dataset_hash !== plan.dataset_hash;
    const pending = run?.status === 'awaiting_result';
    return `
      <section class="panel" aria-labelledby="colab-title">
        <div class="panel-header">
          <div><h2 id="colab-title" tabindex="-1">Train in Colab</h2><p class="caption">A stronger model using your examples and a free Google GPU.</p></div>
          ${badge('Free GPU','good')}
        </div>
        ${pending?colabSteps(run,stale):''}
        ${!pending||stale?`
          <div class="inline-actions ${pending?'spacer':''}">
            <button class="button ${run?'secondary':''}" data-action="colab-prepare" ${!plan.ready?'disabled':''}>${icon('download',16)}Prepare notebook</button>
            <span class="caption">${plan.ready?'You’ll need a Google account and a free T4 runtime.':'Add the missing examples or checks to prepare a notebook.'}</span>
          </div>`:''}
        ${runs.length>1?`
          <details class="training-details spacer"><summary>Colab training history</summary>
            ${runs.map((item,index)=>`
              <button class="training-history" data-action="colab-view" data-id="${esc(item.id)}" aria-pressed="${item.id===run.id}">
                <strong>Colab training ${runs.length-index}</strong>
                <span>${esc(formatDate(item.created_at))}</span>
                ${badge(item.status==='complete'?'Imported':'Waiting for result',item.status==='complete'?'good':'')}
              </button>`).join('')}
          </details>`:''}
      </section>
      ${run?.status==='complete'?comparison(run,'colab'):''}`;
  }

  function comparisonCase(row, index, runId, kind) {
    const label = row.error ? 'Could not finish' : row.review === 'pass' ? 'Looks right' : row.review === 'fail' ? 'Needs work' : 'Needs your review';
    const tone = row.review === 'pass' ? 'good' : row.error || row.review === 'fail' ? 'warn' : '';
    const reviewButton = (review, text) => `<button class="button secondary small" data-action="${kind}-review" data-training="${esc(runId)}" data-id="${esc(row.check_id)}" data-review="${review}" aria-pressed="${row.review===review}">${review==='pass'?icon('check',14):''}${text}</button>`;
    return `
      <article class="comparison-case">
        <div class="panel-header"><h3>Check ${index+1}</h3>${badge(label,tone)}</div>
        <p class="request-text">${esc(row.input)}</p>
        <div class="expected-answer"><span class="example-label">What you wanted</span><p>${esc(row.expected)}</p></div>
        <div class="equal-columns spacer">
          <div class="check-answer"><span class="example-label">Before training</span><p>${esc(row.before||row.before_error||'No complete answer')}</p></div>
          <div class="check-answer trained-answer"><span class="example-label">After training</span><p>${esc(row.after||'No complete answer')}</p></div>
        </div>
        ${row.error?`<div class="error-box">${esc(row.error)} Improve the examples and start a new training.</div>`:`
          <div class="review-actions"><span class="caption">The trained answer…</span>${reviewButton('fail','Needs work')}${reviewButton('pass','Looks right')}</div>`}
      </article>`;
  }

  function localDecision(run, stale, selected) {
    const allRight = run.results.length > 0 && run.results.every(row=>row.review==='pass'&&!row.error);
    return `
      <div class="training-decision">
        <div>
          <strong>${selected?'This training is selected for your draft.':'You decide when to use it.'}</strong>
          <p class="caption">${selected?'Try it, then run Check it and approve a version before live use.':'Only select it when every trained answer looks right. More varied checks give stronger evidence.'}</p>
        </div>
        ${selected?`<a class="button" href="${route('try',state.job.id)}">Try my trained AI ${icon('arrow',16)}</a>`:`
          <button class="button" data-action="training-select" data-id="${esc(run.id)}" ${!allRight||stale?'disabled':''}>Use this training ${icon('arrow',16)}</button>`}
      </div>`;
  }

  function comparison(run, kind='training') {
    const colab = kind === 'colab';
    const stale = run.dataset_hash !== state.job.training_plan.dataset_hash;
    const selected = !colab && state.job.model === `own:${run.id}`;
    return `
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 ${colab?'id="colab-comparison" tabindex="-1"':''}>${colab?'Compare Colab answers':'Did training help?'}</h2>
            <p class="caption">${esc(formatDate(run.created_at))}</p>
          </div>
          ${badge(stale?'Examples have changed':selected?'Selected for your draft':'Ready for review',stale?'warn':selected?'good':'')}
        </div>
        <p>Compare each answer with what you wanted. Mark the trained answers that look right.</p>
        <p class="caption spacer">Both answers use the same base model, instructions, and question. Your separate check questions are kept out of the teaching examples.</p>
        ${stale?`<div class="notice warning spacer"><div><strong>This belongs to an older draft.</strong><p>${colab?'Prepare a new notebook to test your latest examples.':'You can inspect and download it. Train a fresh update before selecting it for your current draft.'}</p></div></div>`:''}
        ${run.results.map((row,index)=>comparisonCase(row,index,run.id,kind)).join('')}
        ${colab?'':localDecision(run,stale,selected)}
        <div class="inline-actions spacer">
          <button class="text-button" data-action="${kind}-export" data-id="${esc(run.id)}">${icon('download',16)}${colab?'Download Colab model':'Download trained model'}</button>
          <span class="caption">${colab?'The downloaded model runs separately on a compatible GPU.':'Includes your private training data and adapter. Public base downloaded separately.'}</span>
        </div>
        <details class="training-details spacer">
          <summary>Training details</summary>
          <p class="caption spacer">${esc(run.base?.id)} · ${colab?'Colab GPU':'CPU LoRA'} · ${run.step} actual steps · ${Number(run.changed_parameters||0).toLocaleString()} changed weights</p>
          <p class="caption">Training loss: ${esc(run.first_loss)} → ${esc(run.last_loss)}. This measures how closely the model fit your teaching answers.</p>
          <p class="caption">Dataset ${esc(run.dataset_hash.slice(0,12))} · frozen when you confirmed permission.</p>
        </details>
      </section>`;
  }

  function render() {
    const j = state.job, plan = j.training_plan, runtime = state.trainingRuntime || {status:'not_installed'};
    const runs = j.trainings || [];
    const running = runs.find(active);
    const focused = runs.find(r=>r.id===chosen.get(j.id)) || runs[0];
    const ready = runtime.status === 'ready';
    return jobShell(`<div class="training-intro"><div><div class="eyebrow">Your examples become a model update</div><h2>Make it learn your way.</h2><p class="lede">Review the lessons, train your AI, then see whether its answers improve.</p></div></div><div id="training-action-error">${errorArea()}</div><div class="training-layout"><div class="stack"><section class="panel"><div class="training-stage"><span class="step-number">1</span><div><h3>Review what it will learn</h3><p class="caption">${plan.teaching_count} teaching examples · ${plan.check_count} separate checks</p></div></div><p class="caption spacer">Use clear, correct answers. Start with a few examples to try training; aim for 20 or more varied examples and several checks before trusting an update.</p>${plan.blockers.length?`<ul class="training-blockers">${plan.blockers.map(b=>`<li>${esc(b)}</li>`).join('')}</ul>`:''}<div class="inline-actions spacer">${button('review-examples','Review examples','book','secondary')}<a class="text-button" href="${route('teach',j.id)}">Add teaching examples ${icon('arrow',14)}</a><a class="text-button" href="${route('check',j.id)}">Add checks ${icon('arrow',14)}</a></div></section>${colabTraining()}<section class="panel"><div class="training-stage"><span class="step-number">2</span><div><h3>Train on this laptop</h3><p class="caption">A small local model. Your examples stay here.</p></div></div>${!ready?`<div class="training-setup spacer"><strong>${esc(runtime.phase)}</strong>${runtime.status==='installing'?'<div class="loading-answer"><span class="spinner" aria-hidden="true"></span><span role="status">Setting up… You can leave this tab. Keep Own running.</span></div>':`<p class="caption spacer">One-time setup installs the CPU tools and downloads the public starter model, about 270 MB plus dependencies. Allow about 2 GB of disk space and an internet connection. Your examples stay here.</p>${runtime.error?`<div class="error-box">${esc(runtime.error)}</div>`:''}<button class="button secondary spacer" data-action="setup-training">Set up local training ${icon('download',16)}</button>`}</div>`:running?`<div class="training-progress spacer" role="status"><strong>${esc(running.phase)}</strong><div class="progress-row"><progress value="${running.step}" max="${running.total_steps}" aria-label="Completed training steps"></progress><span class="caption">${running.step} of ${running.total_steps} steps</span></div><p class="caption">Your approved version is kept. Keep Own open; you can use other tabs.</p><button class="button secondary spacer" data-action="cancel-training" data-id="${running.id}" ${running.status==='cancelling'?'disabled':''}>${running.status==='cancelling'?'Stopping…':'Stop training'}</button></div>`:`<div class="inline-actions spacer"><button class="button" data-action="start-training" ${!plan.ready||runtime.busy?'disabled':''}>${icon('spark',16)}Train my AI</button><span class="caption">${runtime.busy?'Your laptop is already training another job.':plan.ready?'Your examples are ready to review and train.':'Add the missing examples first.'}</span></div>`}</section>${focused&&!active(focused)&&focused.status!=='complete'?`<div class="notice warning"><div><strong>${focused.status==='cancelled'?'Training stopped':'This training did not finish'}</strong><p>${esc(focused.error||'Your examples are safe. Start a new training when you are ready.')}</p></div></div>`:''}${focused?.status==='complete'?comparison(focused):!running?'<div class="panel training-placeholder"><div class="training-stage"><span class="step-number">3</span><div><h3>Compare your local training</h3><p class="caption">Before and after answers appear here when training on your laptop finishes.</p></div></div></div>':''}</div><aside class="stack"><section class="panel mini-note"><div class="job-icon">${icon('shield')}</div><h3 class="spacer">One shared base.<br>Your own training.</h3><p class="spacer">Each business starts with the same model. Its teaching examples and saved model updates stay separate.</p><hr class="rule"><strong>A small local starter</strong><p class="caption spacer">SmolLM2 · 135M · English. It makes real training possible on this laptop, with limited answer quality. Stronger models need more capable hardware.</p><p class="caption spacer">Reference files help with answers in Try it. Training learns only from your reviewed teaching examples.</p><hr class="rule"><strong>Already use Modal?</strong><p class="caption">Connect your own GPU account.</p><a class="text-button spacer" href="${route('gpu',j.id)}">Set up a stronger model ${icon('arrow',14)}</a></section>${runs.length?`<section class="panel"><h3>Local training history</h3>${runs.map((run,i)=>`<button class="training-history" data-action="view-training" data-id="${run.id}" aria-pressed="${focused?.id===run.id}"><strong>Training ${runs.length-i}</strong><span>${esc(formatDate(run.created_at))}</span>${badge(run.status==='complete'?'Ready to review':run.status==='failed'?'Did not finish':run.status==='interrupted'?'Interrupted':run.status==='cancelled'?'Stopped':'In progress',run.status==='complete'?'good':'')}</button>`).join('')}</section>`:''}</aside></div>`);
  }

  async function submit(type, form, data, jobPath, stillHere) {
    if (type === 'colab-prepare') {
      if (data.permission !== 'on') throw new Error('Confirm you have permission to share this training data with Google Colab.');
      const run = await api(`${jobPath}/colab/runs`, {
        method:'POST', body:{dataset_hash:form.dataset.dataset,permission:true},
      });
      if (stillHere()) {
        chosenColab.set(state.job.id,run.id);
        await refreshJob();
      }
      if (stillHere()) await context.download(`${jobPath}/colab/runs/${run.id}/notebook`,notebookName);
      if (stillHere()) {
        closeModal();
        document.getElementById('colab-title')?.focus();
        notify('Notebook downloaded. Open it in Google Colab.');
      }
      return true;
    }
    if (type === 'colab-import') {
      const file = data.result;
      if (!file?.size || !file.name.toLowerCase().endsWith('.zip')) {
        throw new Error('Choose the result ZIP downloaded from Colab.');
      }
      if (file.size > resultLimit) throw new Error('This ZIP is larger than 64 MB. Choose the original result ZIP from Colab.');
      const run = await api(`${jobPath}/colab/runs/${form.dataset.run}/result`,{method:'POST',file,timeout:60000});
      if (stillHere()) {
        chosenColab.set(state.job.id,run.id);
        await refreshJob();
      }
      if (stillHere()) {
        closeModal();
        document.getElementById('colab-comparison')?.focus();
        notify('Model imported. Compare its answers below.');
      }
      return true;
    }
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

  async function handleColab(action, target, path, here) {
    const {id, training, review} = target.dataset;
    if (action === 'colab-prepare') {prepareColabDialog();return true;}
    if (action === 'colab-import') {importColabDialog(id);return true;}
    if (action === 'colab-view') {
      chosenColab.set(state.job.id,id);
      if (await refreshJob() && here()) {
        (document.getElementById('colab-comparison') || document.getElementById('colab-title'))?.focus();
      }
      return true;
    }
    if (!['colab-notebook','colab-review','colab-export'].includes(action)) return false;
    target.disabled=true;
    try {
      if (action === 'colab-notebook') {
        await context.download(`${path}/colab/runs/${id}/notebook`,notebookName);
        if (here()) notify('Notebook downloaded. Keep it private.');
      } else if (action === 'colab-review') {
        await api(`${path}/colab/runs/${training}/review`,{method:'POST',body:{check_id:id,review}});
        if (here() && await refreshJob() && here()) {
          const buttons = document.querySelectorAll('[data-action="colab-review"]');
          [...buttons].find(button=>button.dataset.id===id&&button.dataset.training===training&&button.dataset.review===review)?.focus();
          notify('Your review is saved.');
        }
      } else {
        context.confirmAction(
          'Download your Colab model?',
          'The ZIP includes your private teaching data, checks, and trained model update. Keep it private. The included runner downloads the base model separately and needs a compatible GPU.',
          'Download Colab model',
          async()=>{
            const title = document.getElementById('dialog-title');
            const dialogIsCurrent = ()=>here()&&title?.isConnected&&title.closest('dialog')?.open;
            try {
              await context.download(`${path}/colab/runs/${id}/export`,'acewyn-colab-model.zip');
            } catch (error) {
              if (dialogIsCurrent()) throw error;
              return;
            }
            if (dialogIsCurrent()) {closeModal();notify('Colab model downloaded. Keep it private.');}
          },
        );
      }
      return true;
    } finally {
      if (target.isConnected) target.disabled=false;
    }
  }

  async function handle(action, target) {
    const serial=state.serial, path=state.job?jobBase():null;
    const here=()=>serial===state.serial;
    if(action.startsWith('colab-'))return handleColab(action,target,path,here);
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
