import {createTrainingUI} from './training.js';
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[character]));
const paths = {
  home:'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
  jobs:'M8 6V4h8v2M3 7h18v13H3ZM3 12a26 26 0 0 0 18 0M11 12h2v3h-2Z',
  book:'M4 4h7a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4ZM20 4h-3a3 3 0 0 0-3 3v14a4 4 0 0 1 4-2h2Z',
  plus:'M12 5v14M5 12h14', arrow:'M5 12h14m-5-5 5 5-5 5', back:'M19 12H5m5-5-5 5 5 5',
  check:'m5 12 4 4L19 6', close:'m6 6 12 12M6 18 18 6', upload:'M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6',
  shield:'m12 3 8 3v6c0 4-5 8-8 9-3-1-8-5-8-9V6Zm-4 9 3 3 5-6',
  file:'M14 3H5v18h14V8Zm0 0v5h5M8 12h8M8 16h6',
  spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z',
  settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2',
  clock:'M12 8v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0', download:'M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4',
  info:'M12 11v6m0-10v.1M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0', edit:'m15 4 5 5M4 20l5-1L21 7l-5-5L4 14Z',
};
const icon = (name, size=19) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.spark}"/></svg>`;
const state = {token:'', workspaces:[], engine:{connected:false,models:[]}, workspace:null, job:null, view:'home', route:'', dirty:false, loading:false, polling:null, serial:0, requests:new Map(), busy:false};
const main = $('#main');
const modal = $('#dialog');
let toastTimer;
let modalTrigger;
let modalCallback = null;

function notify(message, error=false) {
  clearTimeout(toastTimer);
  const toast = $('#toast');
  toast.textContent = message;
  toast.className = `toast${error ? ' error' : ''}`;
  toast.hidden = false;
  toastTimer = setTimeout(() => { toast.hidden = true; }, 5000);
}

async function api(path, {method='GET', body, file, timeout=20000}={}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const headers = {'X-Own-Token': state.token};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {method, headers, body:file || (body === undefined ? undefined : JSON.stringify(body)), signal:controller.signal});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'This action could not finish. Refresh the app and try again.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('This is taking longer than expected. Your saved work is safe. Check the connection before trying again.');
    if (error instanceof TypeError) throw new Error('The local app is not connected. Open START.cmd, then try again. Your input is still here.');
    throw error;
  } finally { clearTimeout(timer); }
}

const base = () => `/api/workspaces/${state.workspace.id}`;
const jobBase = () => `${base()}/jobs/${state.job.id}`;
const route = (view='home', job=null) => `#w/${state.workspace.id}/${job ? `j/${job}/${view}` : view}`;
const formatDate = value => new Intl.DateTimeFormat(undefined, {month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(value));
const number = value => new Intl.NumberFormat().format(value);
const badge = (label, tone='') => `<span class="badge ${tone}">${esc(label)}</span>`;
const button = (action, label, glyph='', variant='') => `<button class="button ${variant}" data-action="${action}">${glyph ? icon(glyph,16) : ''}${label}</button>`;
const modelName = model => model?.startsWith('own:') ? 'Your trained AI · local starter' : model;
function modelOptions(selected) {
  return (!selected?'<option value="">Train it first, or choose a local model</option>':'') +
    (selected?.startsWith('own:')?`<option value="${esc(selected)}" selected>Your trained AI · local starter</option>`:'') +
    (selected&&!selected.startsWith('own:')&&!state.engine.models.some(m=>m.name===selected)?`<option value="${esc(selected)}">${esc(selected)} — not currently available</option>`:'') +
    state.engine.models.map(m=>`<option value="${esc(m.name)}" ${m.name===selected?'selected':''}>${esc(m.name)}</option>`).join('');
}
const errorArea = () => '<div class="error-box form-errors" role="alert"></div>';
function field(name, label, value='', {type='text', help='', required=true, max=4000, short=false}={}) {
  const id = `field-${name}`;
  const attrs = `id="${id}" name="${name}" ${required ? 'required' : ''} maxlength="${max}" aria-describedby="${id}-help ${id}-error"`;
  const control = type === 'textarea' ? `<textarea ${attrs} class="${short ? 'short' : ''}" rows="4">${esc(value)}</textarea>` : `<input ${attrs} type="${type}" value="${esc(value)}" autocomplete="off">`;
  return `<div class="field"><label for="${id}">${esc(label)}</label>${control}<small id="${id}-help">${esc(help)}</small><div class="form-error" id="${id}-error"></div></div>`;
}
function empty(title, description, action='', label='', glyph='spark') {
  return `<div class="empty"><div class="empty-icon">${icon(glyph,23)}</div><h3>${esc(title)}</h3><p>${esc(description)}</p>${action ? button(action,label,'plus') : ''}</div>`;
}
function openModal(title, content, callback=null) {
  modalTrigger = document.activeElement;
  modalCallback = callback;
  $('#dialog-content').innerHTML = `<div class="dialog-head"><h2 id="dialog-title">${esc(title)}</h2><button class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></div><div class="dialog-body">${content}</div>`;
  if (!modal.open) modal.showModal();
  requestAnimationFrame(() => ($('[data-initial-focus]',modal) || $('input,textarea,select',modal) || $('[data-action="close-modal"]',modal))?.focus());
}
function closeModal() { modal.close(); }
modal.addEventListener('close', () => { modalCallback = null; if (modalTrigger?.isConnected) modalTrigger.focus(); });
function confirmAction(title, description, label, callback) {
  openModal(title, `<p>${esc(description)}</p>${errorArea()}<div class="form-actions"><button class="button secondary" data-action="close-modal" data-initial-focus>Cancel</button><button class="button" data-action="confirm-modal">${esc(label)}</button></div>`, callback);
}

function renderRail() {
  $('#workspace-picker').innerHTML = state.workspaces.length ? `<div class="workspace-select"><label for="workspace-select">Your business</label><select id="workspace-select" aria-label="Choose your business">${state.workspaces.map(w=>`<option value="${w.id}" ${w.id===state.workspace?.id?'selected':''}>${esc(w.name)}</option>`).join('')}</select><button class="text-button" data-action="new-workspace">${icon('plus',13)}Add a business</button></div>` : '';
  const w = state.workspace;
  $('#navigation').innerHTML = w ? `<div class="nav-heading">WORKSPACE</div>${[
    ['home','home','Overview'], ['jobs','jobs','Your jobs'], ['library','book','Business knowledge']
  ].map(([view,glyph,label])=>`<a class="nav-link ${(state.view===view || (view==='jobs'&&state.job))?'active':''}" href="${route(view)}">${icon(glyph)}${label}${view==='jobs'?`<span class="nav-count">${w.jobs.length}</span>`:''}</a>`).join('')}<button class="nav-link text-button" data-action="connection">${icon('settings')}AI connection</button>` : `<div class="nav-heading">YOUR FIRST STEP</div><span class="nav-link active">${icon('home')}Welcome to Own</span>`;
  $('#connection-label').textContent = state.engine.connected ? (state.engine.models.length ? 'Local AI connected' : 'Choose a local model') : 'Connect your local AI';
}

function welcome() {
  document.title = 'Welcome — Own';
  return `<div class="welcome"><div class="welcome-intro"><div class="eyebrow">Your expertise. Your intelligence.</div><h1>Give your business<br>an AI of its own.</h1><p class="lede">Show it how you work. Correct it in your own words.<br>Stay in control as you make it better.</p></div><div class="welcome-composition"><div class="welcome-form"><h2>First, a home for your work.</h2><p class="caption spacer">Create a workspace for your business. You can add more businesses later.</p><form data-form="workspace" novalidate class="spacer">${field('name','What’s your business called?','',{help:'Use a business, team or project name.',max:100})}${errorArea()}<button class="button full" type="submit">Create my workspace ${icon('arrow',17)}</button></form><div class="welcome-divider">or take a look first</div><button class="button secondary full" data-action="sample">Explore a sample business ${icon('arrow',16)}</button><div id="sample-error">${errorArea()}</div></div><div class="welcome-guide"><div class="job-icon">${icon('spark',23)}</div><h3 class="guide-title spacer">You know the job.<br>We make teaching it simple.</h3>${[
    ['1','Show it your way','Describe a job and share a few good examples.'],['2','Give it a try','Ask it to do the work. Fix anything it gets wrong.'],['3','Check before you change','Review real results, then decide what to use.']
  ].map(([n,title,description])=>`<div class="lesson-step"><span class="step-number">${n}</span><div><strong>${title}</strong><p>${description}</p></div></div>`).join('')}<div class="welcome-bottom">${icon('shield',16)}Stored on this laptop. No account needed.</div></div></div><p class="caption spacer">Teach, train and check on this laptop. The small local starter supports real training; cloud deployment is a later step.</p></div>`;
}

function jobCard(job) {
  return `<article class="panel job-card"><div class="inline-actions"><div class="job-icon">${icon('jobs')}</div>${badge(job.active_version_id?'Approved version ready':'Getting started',job.active_version_id?'good':'')}</div><h3>${esc(job.name)}</h3><p>${esc(job.goal)}</p><div class="job-card-bottom"><span class="caption">${job.model ? esc(modelName(job.model)) : 'Choose a local model'}</span><a href="${route('teach',job.id)}">Open job ${icon('arrow',15)}</a></div></article>`;
}
function home(jobsOnly=false) {
  const w = state.workspace;
  document.title = `${jobsOnly ? 'Your jobs' : w.name} — Own`;
  return `<div class="page-heading"><div><div class="eyebrow">${esc(w.name)}</div><h1>${jobsOnly?'Your jobs':'Your AI starts with what you know.'}</h1><p class="lede">${jobsOnly?'Give each job a clear purpose, a few examples and a way to check its work.':'A place to turn your everyday expertise into useful business AI.'}</p></div><div class="heading-actions">${button('new-job','Create a job','plus')}</div></div>${!jobsOnly?`<div class="learning-path"><div class="path-node"><span class="step-number">1</span><span><strong>Teach it</strong><small>Show good work</small></span></div><span class="path-connector"></span><div class="path-node"><span class="step-number">2</span><span><strong>Try it</strong><small>Make it your own</small></span></div><span class="path-connector"></span><div class="path-node"><span class="step-number">3</span><span><strong>Check it</strong><small>Approve with confidence</small></span></div></div>`:''}<div class="section-heading"><h2>${jobsOnly?'All jobs':'Your jobs'} <span class="caption">${number(w.jobs.length)}</span></h2>${!jobsOnly&&w.jobs.length?`<a class="caption" href="${route('jobs')}">View all ${icon('arrow',14)}</a>`:''}</div>${w.jobs.length?`<div class="grid-jobs">${w.jobs.map(jobCard).join('')}</div>`:`<div class="panel">${empty('What should your AI help with?','Start with something you do often: answer questions, prepare a draft, or pull facts from text.','new-job','Create your first job','jobs')}</div>`}${!jobsOnly?`<div class="two-column spacer"><div class="panel mini-note"><div class="panel-header"><h3>A shared reference shelf</h3>${icon('book')}</div><p>Add your policies, notes and business information. Your jobs can use relevant passages when answering.</p><a class="text-button spacer" href="${route('library')}">${w.sources.length?`${number(w.sources.length)} file${w.sources.length===1?'':'s'} in your library`:'Add business knowledge'} ${icon('arrow',15)}</a></div><div class="panel mini-note"><div class="panel-header"><h3>You make the final call</h3>${icon('shield')}</div><p>Changes stay in a draft until you check and approve them. You can return to an earlier approved version.</p></div></div>`:''}`;
}

function jobShell(content) {
  const j = state.job;
  return `<a class="back-link" href="${route('jobs')}">${icon('back',15)}Your jobs</a><div class="page-heading job-heading"><div><h1>${esc(j.name)}</h1><p class="lede">${esc(j.goal)}</p></div><div class="job-status">${badge(j.active_version_id?'Approved version available':'Working draft',j.active_version_id?'good':'')}</div></div><nav class="tabbar" aria-label="Job steps">${[['teach','Teach it'],['train','Train it'],['try','Try it'],['check','Check it'],['versions','Versions']].map(([view,label],i)=>`<a class="tab-link ${state.view===view?'active':''}" href="${route(view,j.id)}" ${state.view===view?'aria-current="page"':''}><span class="tab-index">0${i+1}</span>${label}</a>`).join('')}</nav>${content}`;
}

function teach() {
  const j = state.job, teaching = j.examples.filter(e=>e.kind==='teach');
  return jobShell(`<div class="two-column"><section class="panel"><div class="panel-header"><h2>Tell it how you work.</h2>${icon('edit')}</div><p class="caption">Use the same words you would use with a new colleague.</p><form data-form="instructions" data-revision="${j.revision}" novalidate class="spacer">${field('goal','What is the job?',j.goal,{type:'textarea',max:1500,short:true})}${field('instructions','Anything it should always remember?',j.instructions,{type:'textarea',required:false,help:'For example: be friendly, keep replies short, and ask if information is missing.',max:4000})}<div class="field"><label for="model-select">Which local AI should do the work?</label><select name="model" id="model-select" aria-describedby="model-help">${modelOptions(j.model)}</select><small id="model-help">${j.model.startsWith('own:')?'Your saved training runs on this laptop. Manage it in Train it.':state.engine.models.length?'Runs through Ollama on this laptop.':'No installed models found. Open AI connection for setup.'}</small><button type="button" class="text-button" data-action="connection">Check AI connection ${icon('arrow',13)}</button></div>${errorArea()}<div class="form-actions"><span class="caption" id="save-status">Saved instructions</span><button class="button" type="submit">Save instructions ${icon('check',16)}</button></div></form></section><div class="stack"><section class="panel"><div class="panel-header"><h3>Show a good example</h3>${badge(`${teaching.length} saved`)}</div><p class="caption">A request and the answer you would want. Your AI can refer to these examples.</p>${teaching.length?`<div class="spacer">${teaching.slice(-3).reverse().map(e=>`<div class="example"><span class="example-label">Someone asks</span><p>${esc(e.input)}</p><span class="example-label">A good answer</span><p>${esc(e.output)}</p></div>`).join('')}</div>`:''}<button class="button secondary full spacer" data-action="add-teach">${icon('plus',16)}Add a teaching example</button><button class="text-button spacer" data-action="review-examples">Review or edit all examples ${icon('arrow',14)}</button></section><div class="notice">${icon('info')}<div><strong>Teaching starts with examples.</strong><p>Examples help guide your answers. Open Train it to turn your reviewed examples into a real model update and compare its results.</p></div></div><a class="text-button" href="${route('library')}">${icon('book',17)}Add reference files to your business library ${icon('arrow',14)}</a></div></div>`);
}

function referencesMarkup(references) {
  if (!references?.length) return '<p class="caption spacer">No matching reference passages were supplied. Review company-specific facts carefully.</p>';
  return `<details class="sources"><summary>${references.length} reference passage${references.length===1?'':'s'} supplied to the AI</summary><p class="caption spacer">These are the passages it received, not independently verified citations.</p>${references.map(r=>`<div class="source-passage"><strong>[${esc(r.id)}] ${esc(r.title)}</strong>${esc(r.passage)}</div>`).join('')}</details>`;
}
function answerMarkup(run) {
  return `<div class="panel-header"><h2>Here’s its answer.</h2>${badge(run.version_id?'Approved version':'Draft answer')}</div><div class="request-text">${esc(run.input)}</div><div class="answer">${esc(run.output)}</div>${referencesMarkup(run.references)}<div class="answer-meta"><span>${esc(modelName(run.model))} · ${(run.duration_ms/1000).toFixed(1)} seconds</span>${run.corrected_output?badge('Correction saved','good'):`<button class="button secondary small" data-action="correct" data-id="${run.id}">${icon('edit',14)}Fix this answer</button>`}</div>${run.corrected_output?`<div class="notice spacer">${icon('check')}<div><strong>Your correction is saved to the draft.</strong><p>Check the updated draft before approving a new version.</p></div></div>`:''}`;
}
function tryView() {
  const j=state.job;
  return jobShell(`<div class="two-column"><div class="stack"><section class="panel"><div class="panel-header"><h2>Give it a real task.</h2>${icon('spark')}</div><form data-form="try" novalidate>${field('input','What would you like it to do?',state.requests.get(j.id)||'',{type:'textarea',help:'Start with a short request. Small local models work best on focused tasks.'})}<div class="field"><label for="run-mode">Try which version?</label><select name="mode" id="run-mode"><option value="draft">Current draft</option>${j.active_version_id?'<option value="live">Approved version</option>':''}</select></div>${errorArea()}<div class="form-actions"><button class="button" type="submit">Try my AI ${icon('arrow',16)}</button></div></form></section><section class="panel" id="answer-panel" aria-live="polite">${j.runs.length?answerMarkup(j.runs[0]):empty('Your first answer will appear here.','Try a task, review the answer and teach it what good work looks like.','','','spark')}</section></div><aside class="stack"><div class="panel mini-note"><div class="job-icon">${icon('edit')}</div><h3>Not quite right? Show it.</h3><p class="spacer">Choose <strong>Fix this answer</strong> and write the answer you wanted. We’ll save it as a teaching example in your draft.</p><hr class="rule"><p>Relevant reference passages use keyword matching. Ollama requests can also include up to two teaching examples; your trained AI uses its saved weights instead. Check company facts carefully.</p></div><section class="panel"><div class="panel-header"><h3>Recent requests</h3>${icon('clock',17)}</div>${j.runs.length?j.runs.slice(0,5).map(r=>`<div class="history-item"><p>${esc(r.input)}</p><small>${esc(formatDate(r.created_at))} · ${r.version_id?'Approved':'Draft'}</small></div>`).join(''):'<p class="caption">Your recent requests will be saved here.</p>'}</section></aside></div>`);
}

function evaluationMarkup(evaluation) {
  const stale = evaluation.fingerprint !== state.job.fingerprint;
  const completed = evaluation.results.filter(r=>r.output || (r.error && r.error!=='Waiting for the model.')).length;
  const passed = evaluation.results.filter(r=>r.review==='pass').length;
  return `<section class="panel check-card"><div class="panel-header"><div><h3>${evaluation.status==='running'?'Your AI is trying the checks…':'Review its work'}</h3><p class="caption">${esc(formatDate(evaluation.created_at))}</p></div>${badge(stale?'Draft has changed':evaluation.status==='running'?'Running':`${passed} of ${evaluation.results.length} marked right`,stale?'warn':'')}</div>${stale?'<div class="notice warning"><div><strong>These results belong to an older draft.</strong><p>Run checks again before approving your current instructions, examples and files.</p></div></div>':''}${evaluation.status==='running'?`<div class="progress-row"><progress value="${completed}" max="${evaluation.results.length}" aria-label="Completed checks"></progress><span class="caption">${completed} of ${evaluation.results.length} completed</span></div>`:''}<p class="caption spacer">Compare each answer with your expected result. Your review is the judgment; the app does not score its own correctness.</p></section>${evaluation.results.map((r,index)=>`<section class="panel check-card"><div class="panel-header"><h3>Check ${index+1}</h3>${badge(r.error?'Not completed':r.review==='pass'?'Looks right':r.review==='fail'?'Needs work':'Needs your review',r.review==='pass'?'good':r.review==='fail'?'warn':'')}</div><p class="request-text">${esc(r.input)}</p><div class="equal-columns"><div class="check-answer"><span class="example-label">What good looks like</span><p>${esc(r.expected)}</p></div><div class="check-answer"><span class="example-label">Your AI’s answer</span><p>${esc(r.output || r.error || 'Waiting for the model…')}</p></div></div><div class="review-actions"><button class="button ${r.review==='pass'?'':'secondary'} small" data-action="review" data-evaluation="${evaluation.id}" data-id="${r.check_id}" data-review="pass" ${r.error||evaluation.status==='running'?'disabled':''}>${icon('check',14)}Looks right</button><button class="button secondary small" data-action="review" data-evaluation="${evaluation.id}" data-id="${r.check_id}" data-review="fail" ${r.error||evaluation.status==='running'?'disabled':''}>Needs work</button></div></section>`).join('')}`;
}
function checkView() {
  const j=state.job, checks=j.examples.filter(e=>e.kind==='check'), latest=j.evaluations[0];
  return jobShell(`<div class="page-heading"><div><h2>Check it on something new.</h2><p class="caption spacer">Use up to 10 requests you haven’t used for teaching. These stay out of teaching and training exports.</p></div><div class="heading-actions">${checks.length<10?button('add-check','Add a check','plus','secondary'):badge('10-check limit')}<button class="button" data-action="run-checks" ${checks.length===0||latest?.status==='running'?'disabled':''}>${icon('check',16)}Run ${checks.length||''} check${checks.length===1?'':'s'}</button></div></div><div id="check-action-error">${errorArea()}</div>${latest?evaluationMarkup(latest):`<div class="panel">${checks.length?`<h3>${checks.length} check example${checks.length===1?'':'s'} ready</h3><p class="caption spacer">Run checks to see real model answers, then review each result.</p><div class="spacer">${checks.map(e=>`<div class="example"><span class="example-label">Request</span><p>${esc(e.input)}</p><span class="example-label">What good looks like</span><p>${esc(e.output)}</p></div>`).join('')}</div>`:empty('What should good work look like?','Add a new request and an example of the result you expect. Start with one check, then add more varied cases.','add-check','Add your first check','check')}</div>`}<div class="notice spacer">${icon('shield')}<div><strong>A few checks are a starting point.</strong><p>Passing these examples does not prove reliability across all work. Add varied and difficult cases as you learn.</p></div></div><div class="form-actions"><a class="button secondary" href="${route('versions',j.id)}">Review versions ${icon('arrow',15)}</a></div>`);
}
function versionsView() {
  const j=state.job, latest=j.evaluations[0];
  const ready=latest&&latest.fingerprint===j.fingerprint&&latest.status!=='running'&&latest.results.length&&latest.results.every(r=>r.review==='pass'&&!r.error);
  return jobShell(`<div class="two-column"><div class="stack"><section class="panel"><div class="panel-header"><h2>Your current draft</h2>${badge(ready?'Checks reviewed':'Not ready to approve',ready?'good':'')}</div><p class="caption">Approving saves a fixed copy of your instructions, model choice, examples and reference files. New edits stay in the draft.</p><div class="inline-actions spacer">${badge(`${j.examples.filter(e=>e.kind==='teach').length} teaching examples`)}${badge(`${state.workspace.sources.length} reference files`)}</div><div class="form-actions"><button class="button" data-action="approve" ${ready?'':'disabled'}>${icon('check',16)}Approve this version</button></div>${!ready?`<p class="caption spacer">Run checks on the current draft, then mark every result “Looks right” to enable approval. <a href="${route('check',j.id)}">Go to checks</a></p>`:''}</section><section class="panel"><div class="panel-header"><h2>Approved versions</h2>${icon('clock')}</div>${j.versions.length?j.versions.map(v=>`<div class="version-row"><div><h3>Version ${v.number} ${v.id===j.active_version_id?badge('In use','good'):''}</h3><p>${esc(formatDate(v.created_at))}<br>${esc(v.snapshot.job.model)} · ${v.snapshot.examples.length} examples · ${v.snapshot.sources.length} files</p></div>${v.id===j.active_version_id?badge('Current version','good'):`<button class="button secondary small" data-action="activate" data-id="${v.id}" data-number="${v.number}">Use version ${v.number}</button>`}</div>`).join(''):empty('You are in control of updates.','Your first approved version will appear here. Keep earlier versions and switch back when needed.','','','shield')}</section></div><aside class="stack"><section class="panel mini-note"><div class="job-icon">${icon('download')}</div><h3>Your work goes with you.</h3><p class="spacer">Export your business knowledge, examples, check results and saved versions.</p><button class="button secondary full spacer" data-action="export">${icon('download',16)}Download workspace</button><hr class="rule"><p>The export includes data and configuration. Model weights and a trained adapter are not included in this first edition.</p></section><div class="notice">${icon('info')}<div><strong>Versions are saved configurations.</strong><p>Model weight training, cloud deployment and automatic base-model migration are future steps.</p></div></div></aside></div>`);
}
function library() {
  const w=state.workspace;
  return `<div class="page-heading"><div><div class="eyebrow">${esc(w.name)}</div><h1>What your business knows.</h1><p class="lede">Give your AI a reference shelf: policies, notes and information it should use.</p></div><div class="heading-actions">${button('add-note','Write a note','plus')}</div></div><div class="two-column"><section class="panel"><div class="panel-header"><h2>Reference files</h2>${badge(`${w.sources.length} saved`)}</div>${w.sources.length?w.sources.map(s=>`<div class="file-row"><div class="job-icon">${icon('file')}</div><div class="file-info"><strong>${esc(s.title)}</strong><p>${number(s.content.length)} characters · ${esc(formatDate(s.created_at))}</p><button class="text-button" data-action="view-source" data-id="${s.id}">Read note ${icon('arrow',13)}</button></div></div>`).join(''):empty('A little context goes a long way.','Add information you would share with a new colleague. It is available only to jobs in this workspace.','','','book')}</section><aside class="stack"><section class="panel"><h3>Add a reference file</h3><p class="caption spacer">Text files work best in this first edition.</p><button class="drop-area spacer" data-action="choose-file" id="drop-area">${icon('upload',25)}<strong>Choose a file or drop it here</strong><small>.txt, .md or .csv · up to 1 MB</small></button><input type="file" id="file-input" class="hidden-input" accept=".txt,.md,.csv" aria-label="Upload a business reference file"><div id="upload-status" class="upload-status" role="status"></div><div id="upload-error">${errorArea()}</div><p class="caption">UTF-8 text, up to 200,000 characters. PDF and Word support comes later.</p></section><div class="notice">${icon('shield')}<div><strong>Saved on this laptop.</strong><p>This edition has no accounts or encryption. Use sample information while we build production security.</p></div></div></aside></div>`;
}

async function loadRoute() {
  clearTimeout(state.polling);
  const id=++state.serial;
  const parts=location.hash.slice(1).split('/');
  const workspaceId=parts[0]==='w'?parts[1]:state.workspaces[0]?.id;
  const jobId=parts[2]==='j'?parts[3]:null;
  const view=jobId?(parts[4]||'teach'):(parts[2]||'home');
  if (!workspaceId) {state.workspace=null;state.job=null;renderRail();main.innerHTML=welcome();return;}
  state.loading=true;
  try {
    const workspace=await api(`/api/workspaces/${workspaceId}`);
    const job=jobId?await api(`/api/workspaces/${workspaceId}/jobs/${jobId}`):null;
    const trainingRuntime=job?await api('/api/training/runtime'):null;
    if(id!==state.serial)return;
    const changedRoute=state.route!==location.hash;
    state.workspace=workspace;state.job=job;state.trainingRuntime=trainingRuntime;state.view=view;state.route=location.hash;state.dirty=false;
    renderRail();renderView();
    if(changedRoute){window.scrollTo({top:0});main.focus({preventScroll:true});}
    if(job&&(job.evaluations[0]?.status==='running'||job.trainings.some(trainingUI.active)||trainingRuntime.status==='installing'||trainingRuntime.busy))pollChecks();
  } catch(error) {
    if(id!==state.serial)return;
    main.innerHTML=`<div class="panel">${empty('We couldn’t open this workspace.',error.message)}<a class="button secondary" href="#home">Back to your workspace</a></div>`;
  } finally {if(id===state.serial)state.loading=false;}
}
function renderView() {
  const titles={teach:'Teach it',train:'Train it',try:'Try it',check:'Check it',versions:'Versions',library:'Business knowledge',jobs:'Your jobs',home:'Overview'};
  $('#breadcrumb').textContent=`${state.workspace.name} / ${state.job ? state.job.name : titles[state.view]||'Overview'}`;
  if(state.job)document.title=`${titles[state.view]||'Job'} · ${state.job.name} — Own`;
  const render=state.job?{teach,train:trainingUI.render,try:tryView,check:checkView,versions:versionsView}[state.view]:{home,jobs:()=>home(true),library}[state.view];
  main.innerHTML=render?render():`<div class="panel">${empty('This page isn’t here.','Use the workspace navigation to continue.')}<a class="button secondary" href="${route()}">Back to overview</a></div>`;
}
function go(hash) {if(location.hash===hash)loadRoute();else location.hash=hash;}
window.addEventListener('hashchange',()=>{
  if(state.dirty){const next=location.hash;history.replaceState(null,'',state.route||'#');confirmAction('Leave unsaved instructions?','Your last saved instructions will stay in place. Leave this page to discard the unsaved changes.','Leave page',async()=>{state.dirty=false;closeModal();go(next);});return;}
  loadRoute();
});

async function refreshJob({render=true}={}) {
  const ws=state.workspace.id, job=state.job.id, serial=state.serial;
  const result=await api(`/api/workspaces/${ws}/jobs/${job}`);
  if(serial!==state.serial||job!==state.job?.id)return false;
  state.job=result;
  if(render)renderView();
  return true;
}
function pollChecks() {
  clearTimeout(state.polling);
  state.polling=setTimeout(async()=>{
    if(!state.job)return;
    try {
      const serial=state.serial;
      const runtime=await api('/api/training/runtime');
      if(serial!==state.serial)return;
      state.trainingRuntime=runtime;
      const updated=await refreshJob({render:!state.dirty&&['train','check','versions'].includes(state.view)});
      if(!updated)return;
      if(state.job.evaluations[0]?.status==='running'||state.job.trainings.some(trainingUI.active)||runtime.status==='installing'||runtime.busy)pollChecks();
      else notify('Your local AI has finished working. Review the results.');
    } catch(error){notify(error.message,true);}
  },2000);
}

function validate(form) {
  let first=null;
  for(const input of form.querySelectorAll('input[required],textarea[required],select[required]')) {
    const invalid=input.type==='checkbox'?!input.checked:!input.value.trim();
    input.setAttribute('aria-invalid',String(invalid));
    const error=$(`#${input.id}-error`);
    if(error)error.textContent=invalid?'Add this information to continue.':'';
    if(invalid&&!first)first=input;
  }
  if(first){first.focus();return false;}return true;
}
async function formAction(form, action) {
  if(!validate(form))return;
  const data=Object.fromEntries(new FormData(form));
  const submit=$('[type="submit"]',form);
  if(submit.disabled)return;
  const error=$('.form-errors',form);error.textContent='';
  const controls=[...form.querySelectorAll('input,textarea,select,button')].map(control=>[control,control.disabled]);
  for(const [control] of controls)control.disabled=true;
  submit.classList.add('busy');
  try {await action(data);} catch(problem){error.textContent=problem.message;notify(problem.message,true);}
  finally {for(const [control,disabled] of controls)control.disabled=disabled;submit.classList.remove('busy');}
}

document.addEventListener('input',event=>{
  const field=event.target;
  if(field.closest('[data-form="instructions"]')){state.dirty=true;$('#save-status').textContent='Unsaved changes';}
  if(field.name==='input'&&field.closest('[data-form="try"]'))state.requests.set(state.job.id,field.value);
  if(field.hasAttribute('aria-invalid'))field.setAttribute('aria-invalid','false');
});
document.addEventListener('change',async event=>{
  if(event.target.id==='workspace-select')go(`#w/${event.target.value}/home`);
  if(event.target.id==='model-select'){state.dirty=true;$('#save-status').textContent='Unsaved changes';}
  if(event.target.id==='file-input'&&event.target.files[0])await upload(event.target.files[0]);
});

document.addEventListener('submit',event=>{
  const form=event.target;if(!form.matches('[data-form]'))return;event.preventDefault();
  const type=form.dataset.form;
  const origin={serial:state.serial,workspace:state.workspace?.id,job:state.job?.id};
  const workspacePath=`/api/workspaces/${origin.workspace}`;
  const jobPath=`${workspacePath}/jobs/${origin.job}`;
  const stillHere=()=>origin.serial===state.serial&&origin.workspace===state.workspace?.id&&origin.job===state.job?.id;
  formAction(form,async data=>{
    if(await trainingUI.submit(type,form,data,jobPath,stillHere))return;
    if(type==='workspace'){
      const workspace=await api('/api/workspaces',{method:'POST',body:data});
      state.workspaces.push(workspace);if(!stillHere())return;closeModal();go(`#w/${workspace.id}/home`);notify('Your workspace is ready.');
    } else if(type==='job'){
      const job=await api(`${workspacePath}/jobs`,{method:'POST',body:data});if(!stillHere())return;closeModal();go(route('teach',job.id));notify('Job created. Show it how you work.');
    } else if(type==='instructions'){
      await api(jobPath,{method:'PATCH',body:{revision:Number(form.dataset.revision),changes:data}});if(!stillHere())return;state.dirty=false;await refreshJob();notify('Instructions saved.');
    } else if(type==='example'){
      await api(`${jobPath}/examples`,{method:'POST',body:data});if(!stillHere())return;closeModal();await refreshJob();notify(data.kind==='check'?'Check example saved.':'Teaching example saved to your draft.');
    } else if(type==='note'){
      await api(`${workspacePath}/sources`,{method:'POST',body:data});if(!stillHere())return;closeModal();await loadRoute();notify('Business note saved.');
    } else if(type==='correction'){
      await api(`${jobPath}/runs/${form.dataset.run}/correction`,{method:'POST',body:data});if(!stillHere())return;closeModal();await refreshJob();notify('Correction saved as a teaching example.');
    } else if(type==='try'){
      const jobId=state.job.id,serial=state.serial;
      const panel=$('#answer-panel');panel.innerHTML='<div class="loading-answer" role="status"><span class="spinner" aria-hidden="true"></span><span>Your local AI is working.<br><small>The first answer can take a little longer on a laptop.</small></span></div>';
      try {
        const run=await api(`${jobPath}/try`,{method:'POST',body:data,timeout:195000});
        if(serial!==state.serial||jobId!==state.job?.id)return;
        state.job.runs.unshift(run);panel.innerHTML=answerMarkup(run);notify('Answer ready. Check its work.');
      } catch(error){if(panel.isConnected)panel.innerHTML=empty('Your request is still here.',error.message,'connection','Check AI connection','info');throw error;}
    }
  });
});

function exampleDialog(kind) {
  openModal(kind==='check'?'Add a new check':'Show it a good example',`<p>${kind==='check'?'Use a request you have not used for teaching. The expected answer is kept out of the AI’s input.':'Share a request and the answer you would want a colleague to give.'}</p><form data-form="example" novalidate><input type="hidden" name="kind" value="${kind}">${field('input','Someone asks…','',{type:'textarea',short:true})}${field('output',kind==='check'?'What should a good answer include?':'What would a good answer be?','',{type:'textarea',max:6000})}${errorArea()}<div class="form-actions"><button type="button" class="button secondary" data-action="close-modal">Cancel</button><button type="submit" class="button">Save ${kind==='check'?'check':'example'}</button></div></form>`);
}
async function connectionDialog() {
  openModal('Your local AI connection',`<div class="loading-answer"><span class="spinner" aria-hidden="true"></span>Checking Ollama on this laptop…</div>`);
  const engine=await api('/api/engine');state.engine=engine;renderRail();
  const selector=$('#model-select');
  if(selector){
    const selected=selector.value;
    selector.innerHTML=modelOptions(selected);
    $('#model-help').textContent=engine.models.length?'Runs through Ollama on this laptop.':'No installed models found. Open AI connection for setup.';
  }
  if(!modal.open)return;
  openModal('Your local AI connection',`<div class="notice ${!engine.connected||!engine.models.length?'warning':''}">${icon(engine.models.length?'check':'info')}<div><strong>${esc(engine.message)}</strong><p>${engine.models.length?'Choose a model in a job’s Teach it tab, then save your instructions.':'Ollama runs an open-weight model locally. No paid API key is needed.'}</p></div></div><div class="spacer">${engine.models.length?engine.models.map(m=>`<div class="file-row"><div class="job-icon">${icon('spark')}</div><div class="file-info"><strong>${esc(m.name)}</strong><p>${(m.size/1e9).toFixed(1)} GB · installed locally</p></div></div>`).join(''):`<p class="caption">1. Open the Ollama app on your laptop.<br>2. Run <strong>INSTALL LOCAL MODEL.cmd</strong> in the project folder, or run this command in a terminal:</p><code class="command">ollama pull qwen3:1.7b</code><p class="caption">The suggested model downloads about 1.4 GB. Installation uses the internet; business requests stay local. Speed and answer quality depend on your laptop and the task.</p>`}</div>${errorArea()}<div class="form-actions"><button class="button secondary" data-action="close-modal">Close</button><button class="button" data-action="recheck-connection">Check again</button></div>`);
}

async function upload(file) {
  const status=$('#upload-status'),error=$('#upload-error .error-box'),drop=$('#drop-area');
  if(!status||drop.disabled)return;
  error.textContent='';
  if(!/\.(txt|md|csv)$/i.test(file.name)||file.size>1048576){error.textContent='Choose a .txt, .md or .csv file smaller than 1 MB.';return;}
  const ws=state.workspace.id,serial=state.serial;
  drop.disabled=true;status.textContent=`Saving ${file.name}…`;
  try{const form=new FormData();form.append('file',file);await api(`${base()}/upload`,{method:'POST',file:form});if(serial===state.serial&&ws===state.workspace?.id){await loadRoute();notify('Reference file saved.');}}
  catch(problem){error.textContent=problem.message;status.textContent='File not saved. Choose the file again to retry.';}
  finally{drop.disabled=false;}
}
document.addEventListener('dragover',event=>{if(event.target.closest('#drop-area')){event.preventDefault();$('#drop-area').classList.add('dragging');}});
document.addEventListener('dragleave',event=>{if(event.target.closest('#drop-area'))$('#drop-area').classList.remove('dragging');});
document.addEventListener('drop',event=>{if(event.target.closest('#drop-area')){event.preventDefault();$('#drop-area').classList.remove('dragging');if(event.dataTransfer.files[0])upload(event.dataTransfer.files[0]);}});

async function downloadWorkspace() {
  await downloadFile(`${base()}/export`,'own-workspace.zip');
  closeModal();notify('Workspace export downloaded. Keep it private.');
}
async function downloadFile(path,filename) {
  const response=await fetch(path,{headers:{'X-Own-Token':state.token}});
  if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(error.error||'The export could not finish. Try again.');}
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
}

async function makeSample(buttonElement) {
  buttonElement.disabled=true;buttonElement.classList.add('busy');
  try{
    const ws=await api('/api/workspaces',{method:'POST',body:{name:'Sample business'}});state.workspaces.push(ws);
    const wsbase=`/api/workspaces/${ws.id}`;
    await api(`${wsbase}/sources`,{method:'POST',body:{title:'Sample shop policies — fictional',content:'These are fictional policies for trying Own. Standard delivery takes five working days. Returns are accepted within 30 days of delivery. A receipt is required. Refunds are sent to the original payment method. Support email: hello@example.com.'}});
    const job=await api(`${wsbase}/jobs`,{method:'POST',body:{name:'Answer customer questions',goal:'Write a short, friendly reply using our shop policies. Say when information is missing.'}});
    await api(`${wsbase}/jobs/${job.id}`,{method:'PATCH',body:{revision:1,changes:{instructions:'Use plain language. Do not invent promises or policy details. Keep replies under 80 words.',model:state.engine.models[0]?.name||''}}});
    await api(`${wsbase}/jobs/${job.id}/examples`,{method:'POST',body:{kind:'teach',input:'Can I get my money back on a return?',output:'Yes. Eligible returns are refunded to your original payment method. Please keep your receipt.'}});
    state.requests.set(job.id,'How many days does standard delivery take?');
    go(`#w/${ws.id}/j/${job.id}/teach`);notify('Sample workspace created with fictional information.');
  }catch(error){$('#sample-error .error-box').textContent=error.message;}
  finally{buttonElement.disabled=false;buttonElement.classList.remove('busy');}
}
function roadmap() {
  const rows=[['Local teaching workbench','Business jobs, reference notes, real model answers, corrections, separate checks, approval and data exports.','Available in this edition'],['Train your business model','Reviewed frozen datasets, permission records, actual local LoRA training, comparisons and real adapter export.','Available · small local starter'],['Run it where you choose','Adapter export and standalone CPU runner available. Managed cloud and on-prem deployment are later steps.','Local runner available'],['Improve from real work','Investigate failures, compare fixes, measure quality and cost, then release approved improvements.','Planned'],['Carry your expertise forward','Evaluate new base models, migrate specializations and optionally route difficult requests to approved frontier models.','Planned']];
  openModal('The bigger picture',`<p>One platform for different businesses. Each business keeps its own knowledge, examples and model customization.</p>${rows.map(([title,description,status],i)=>`<div class="roadmap-row"><span class="step-number">${i+1}</span><div class="roadmap-copy"><strong>${title}</strong><p>${description}</p>${badge(status,i===0?'good':'')}</div></div>`).join('')}<div class="form-actions"><button class="button secondary" data-action="close-modal">Back to my workspace</button></div>`);
}

document.addEventListener('click',async event=>{
  if(event.target.closest('.skip')){event.preventDefault();main.focus();return;}
  const target=event.target.closest('[data-action]');if(!target||target.disabled)return;
  const action=target.dataset.action;
  const actionSerial=state.serial;
  const actionJobPath=state.job?jobBase():null;
  if(state.dirty&&action==='add-teach'){
    const form=$('[data-form="instructions"]');
    $('.form-errors',form).textContent='Save your instructions before adding a teaching example. Your changes are still here.';
    notify('Save your instructions first.',true);return;
  }
  try{
    if(await trainingUI.handle(action,target))return;
    if(action==='close-modal')closeModal();
    else if(action==='confirm-modal'){
      const callback=modalCallback;target.disabled=true;target.classList.add('busy');
      try{await callback?.();}finally{target.disabled=false;target.classList.remove('busy');}
    }
    else if(action==='roadmap')roadmap();
    else if(action==='connection'||action==='recheck-connection')await connectionDialog();
    else if(action==='new-workspace')openModal('Add a business',`<p>Each workspace has its own knowledge, jobs and examples. This is a single-owner local edition.</p><form data-form="workspace" novalidate>${field('name','Business name','',{max:100})}${errorArea()}<div class="form-actions"><button class="button secondary" type="button" data-action="close-modal">Cancel</button><button class="button" type="submit">Create workspace</button></div></form>`);
    else if(action==='new-job')openModal('What should your AI help with?',`<p>Start with one job you can describe and check. You can teach it more jobs later.</p><form data-form="job" novalidate>${field('name','Give the job a name','',{max:100,help:'For example: Answer customer questions'})}${field('goal','Describe the work in your own words','',{type:'textarea',max:1500,help:'For example: Draft friendly replies using our delivery and returns policies.'})}${errorArea()}<div class="form-actions"><button class="button secondary" type="button" data-action="close-modal">Cancel</button><button class="button" type="submit">Create job ${icon('arrow',16)}</button></div></form>`);
    else if(action==='add-teach')exampleDialog('teach');
    else if(action==='add-check')exampleDialog('check');
    else if(action==='add-note')openModal('Add business knowledge',`<p>Write or paste information your AI should refer to. New files affect every draft job in this workspace; approved versions keep their saved files.</p><form data-form="note" novalidate>${field('title','Give this note a name','',{max:160})}${field('content','What should it know?','',{type:'textarea',max:200000})}${errorArea()}<div class="form-actions"><button class="button secondary" type="button" data-action="close-modal">Cancel</button><button class="button" type="submit">Save note</button></div></form>`);
    else if(action==='choose-file')$('#file-input').click();
    else if(action==='view-source'){
      const source=state.workspace.sources.find(s=>s.id===target.dataset.id);
      openModal(source.title,`<p class="caption">${number(source.content.length)} characters · saved in this business workspace</p><div class="answer">${esc(source.content)}</div><div class="form-actions"><button class="button secondary" data-action="close-modal">Close note</button></div>`);
    }
    else if(action==='correct'){
      const run=state.job.runs.find(r=>r.id===target.dataset.id);
      openModal('Show it the answer you wanted',`<p>Your correction becomes a teaching example in the draft. The approved version stays unchanged.</p><p class="request-text">${esc(run.input)}</p><form data-form="correction" data-run="${run.id}" novalidate>${field('output','A better answer',run.output,{type:'textarea',max:6000})}${errorArea()}<div class="form-actions"><button class="button secondary" type="button" data-action="close-modal">Cancel</button><button class="button" type="submit">Save correction</button></div></form>`);
    }
    else if(action==='run-checks'){
      target.disabled=true;await api(`${actionJobPath}/evaluations`,{method:'POST',body:{}});if(actionSerial!==state.serial)return;await refreshJob();pollChecks();notify('Checks started. You can review the results here.');
    }
    else if(action==='review'){
      target.disabled=true;await api(`${actionJobPath}/evaluations/${target.dataset.evaluation}/review`,{method:'POST',body:{check_id:target.dataset.id,review:target.dataset.review}});if(actionSerial!==state.serial)return;await refreshJob();notify('Your review is saved.');
    }
    else if(action==='approve')confirmAction('Approve this version?','This saves the current instructions, model choice, examples and files as the version to use for approved requests. Your manual check reviews are a starting point, not a reliability guarantee.','Approve version',async()=>{await api(`${jobBase()}/approve`,{method:'POST',body:{}});closeModal();await refreshJob();notify('Version approved. You can try the approved version now.');});
    else if(action==='activate'){
      const versionId=target.dataset.id, versionNumber=target.dataset.number;
      confirmAction(`Use version ${versionNumber}?`,'Approved requests will use the model, instructions, examples and files saved in this version. Your current draft will be kept.','Use this version',async()=>{await api(`${jobBase()}/activate`,{method:'POST',body:{version_id:versionId}});closeModal();await refreshJob();notify(`Version ${versionNumber} is now in use.`);});
    }
    else if(action==='export')confirmAction('Download your workspace?','The ZIP includes this business’s documents, examples, recent answers, checks and saved configurations. Keep it private. It includes training-ready teaching examples, but no model weights or trained adapter.','Download workspace',downloadWorkspace);
    else if(action==='sample')await makeSample(target);
  }catch(error){
    target.disabled=false;notify(error.message,true);
    const area=modal.open?$('.form-errors',modal):$('#training-action-error .error-box')||$('#check-action-error .error-box');
    if(area)area.textContent=error.message;
  }
});

async function start() {
  try{
    const boot=await api('/api/bootstrap');state.token=boot.csrf_token;state.workspaces=boot.workspaces;
    state.engine=await api('/api/engine');
    if(!location.hash&&state.workspaces.length)history.replaceState(null,'',`#w/${state.workspaces[0].id}/home`);
    await loadRoute();
  }catch(error){main.innerHTML=`<div class="panel">${empty('Open your local workspace.',error.message)}<button class="button secondary" data-action="reload">Try connecting again</button></div>`;}
}
const trainingUI=createTrainingUI({state,api,esc,icon,badge,button,field,errorArea,formatDate,jobShell,jobBase,route,openModal,closeModal,notify,refreshJob,poll:pollChecks,confirmAction,download:downloadFile});
document.addEventListener('click',event=>{if(event.target.closest('[data-action="reload"]'))location.reload();});
await start();
