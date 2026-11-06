# Current prototype verification — 6 November 2026

- The source includes the ivory/olive Acewyn AI redesign, real CPU model training, and the Colab preparation/import/comparison flow.
- The current Python suite has 99 tests. JavaScript syntax checks cover app.js, training.js, and gpu.js.
- The Colab browser regression exercises notebook consent/download, retained invalid-ZIP input, retry, verified synthetic adapter import, expected-answer comparison, saved review, and export. It uses an isolated local app and makes no cloud calls.
- Real free-T4 runs on November 3 trained Qwen3-4B adapters on fictional shop data. The first used 6 lessons and 18 steps, and the second used 12 lessons and 36 steps. Both changed 2,949,120 adapter parameters and were verified and imported.
- On the same two separate checks, retraining changed the delivery answer from “Delivery takes 3-5 working days.” to “Standard delivery takes five working days.” The second run answered the receipt check with “A receipt is required for returns.” Human reviews are still pending. These reused questions provide limited quality evidence.
- A real import exposed the standard Qwen tokenizer file added_tokens.json. The verifier now permits that exact file while preserving archive, hash, request, topology, and finite-weight checks. A regression test covers it.
- The redesigned overview and Train it screens were checked on desktop and at 360/390 px, including image loading, workspace navigation, keyboard dialog opening/closing, focus return, and the saved real Colab comparison.
- Colab results currently support comparison/export. Larger-adapter inference inside Try it, the first actual Modal L4 run, production authentication/encryption, and broad task-quality evaluation remain future work.

The following sections preserve earlier milestone evidence and limits as they were recorded.

## Historical Step 4 GPU workflow verification — 2 November 2026

The supervised workflow is implemented; the **first actual L4/Qwen3-4B run is still pending**. The founder requires free credits only, no out-of-pocket charges. No cloud image, GPU invocation or business-data upload was started. Remaining credits and the provider's net $0 Spend limit have not been confirmed.

- **96 Python tests pass** with `python -m unittest discover -s tests -q`. Coverage includes strict per-run permissions, stale data, one active run, scope, immutable inputs, worker failures, secret boundaries, cancellation uncertainty/recovery, finite safetensors, exact topology, archive bounds, request/base/config/check binding, verified export and preservation of the existing local workflow.
- The installed **Modal 1.6.3** constructs the real App/Function definition locally with one L4, US region, 300-second startup timeout, bounded execution, unique per-run name and no training retries. This creates no app or image remotely and is not a CUDA compatibility test.
- A real offline small-model shared-core run performed **1 optimizer step**, changed **184,320 parameters**, saved/reloaded the adapter and compared the held-out request. Its actual result also passes the final bounded archive verifier, including the trusted Smol topology and exact request hash. This is CPU evidence, not Qwen/L4 evidence.
- Controlled browser flow passes: four unchecked consent gates, measured-step protocol, unconfirmed stop, reconnect-to-stop form, human review, private download, late-response modal preservation, desktop and 390px layouts. Every mutation in this test is intercepted, so displayed GPU answers are explicit test fixtures. Browser screenshots under the task's `work/browser-qa/step4-*.png` are UI verification, not GPU-training proof.
- The existing setup browser flow also passes after moving account details into a disclosure: mask/reveal, invalid token format with retained input, delayed connection response preserving a newer form, permission and allowance validation, and a real local fictional-data package download. Mobile document width380 vs viewport390; no JavaScript errors. No actual account replacement or cloud compute occurs in that flow.
- JavaScript syntax passes for app.js, training.js, gpu.js and both GPU browser scripts. DESIGN.md lint returns zero errors and eight warnings (component minHeight vocabulary and unused component references). Premium strict static audit reports **13 delegated-button findings**, all `affordance.actionless-button`; it cannot resolve the shared data-action dispatcher. These have real handlers; runtime evidence is separate. The strict static audit does **not** pass, and there are zero unresolved ownership findings.
- The already-connected provider workspace was verified with a **real read-only identity lookup** using credentials only in protected storage/process environment. Its name is saved as connection metadata and frozen before any training launch. Recovery replacement must match the recorded workspace; mismatched tokens preserve the old connection. This lookup starts no compute and does not verify credits/billing limits.

Independent read-only review reported three issues, all reproduced with failing regression tests and fixed in one author verification pass:

1. A queue/auth/local-definition failure before app creation could block all future runs forever. The worker now records whether creation was attempted; conclusive pre-launch failures/cancellations are terminal, while uncertain outcomes after an attempt remain blocked for provider recovery.
2. A partial or wrongly shaped adapter could pass structural validation. Trusted metadata from the pinned base configuration now requires every expected q_proj/v_proj A/B tensor, layer and dimension. Qwen's topology is 36 layers, input2560, q-output4096, v-output1024. Acceptance fixtures use the complete model topology. A tiny one-layer forgery is rejected.
3. Revoked credentials could not be replaced while recovering an interrupted job. A separate scoped reconnect-to-stop route validates a replacement token's provider workspace before saving it and immediately attempts termination. It cannot launch training. Wrong-scope tokens are rejected without overwriting the saved connection.

No second independent review was performed after these fixes. The author ran the full 96-test suite, browser recovery regression and real tiny-result validation. Actual L4 execution, Qwen quality, provider net-limit enforcement, remaining credits, actual charges and in-app GPU hosting remain unverified. Earlier milestone evidence below is historical, not a description of current feature availability.

## Historical Step 3 setup verification — 2 November 2026

Scope explicitly chosen by the founder: **no cloud account yet; build setup first**.

- **60 Python tests pass**: existing local training plus GPU scope/consent/staleness, finite planning values, credential redaction, failed-connection preservation, real DPAPI roundtrip, immutable trainer/data packages and explicit launch acknowledgement gates.
- JavaScript syntax checks pass for app.js, training.js, gpu.js and the GPU browser test.
- Installed **Modal 1.6.3** only under ignored data/gpu/environment. Verified its real CLI help and constructed its real local App/Function definition without authentication or remote execution. SDK inspection confirmed connection verification calls read-only AppList and automatic single-module mounting excludes adjacent JSON.
- Actual Windows DPAPI encrypted/decrypted a fictional token pair across vault instances. Tests confirm secrets are absent from status/workspace/model-package exports. No real token pair was available; real authentication remains unverified.
- Browser: account/setup links, mask/reveal, local token-format rejection with retained input, unchecked permission rejection, invalid allowance rejection, local preparation/download without an account, desktop 1280×900 and mobile 390×844. No page JavaScript errors; mobile document width380 vs viewport390. A delayed successful connection response was intercepted in an isolated browser test to verify replacement-dialog input preservation; this is transport testing, not a successful provider authentication.
- Smoke-tested the packaged training core entirely offline on the already-installed small SmolLM2 model: one actual optimizer step changed **184,320 weights**, saved/reloaded an adapter, compared an unseen request and retained the frozen job instructions in the result. This is **not** an L4 test or a Qwen3-4B training claim.
- Caught/fixed real SDK nested-function incompatibility, missing frozen instructions in the portable result, and trainer code changing after package preparation. Immutable package regression observed RED→GREEN.
- Final downloaded-package source hashes were verified against its manifest. Running its entrypoint without acknowledgement flags failed locally before importing the provider client. Actual app status confirms no connected account and remote training disabled.
- Design lint completed with exit code 0. Strict premium static audit reports **11 delegated-action button findings**, all `affordance.actionless-button`; its scanner cannot follow the shared data-action dispatcher. No unresolved ownership findings. The audit is not clean; runtime evidence is recorded separately.
- Independent read-only review found no critical/important issues. Its two minor suggestions were addressed as acceptance evidence: more accurate resource/timeout pricing language and a targeted delayed-connection browser case. The reviewer independently passed 10 isolated setup/package tests.

No cloud image was built, no remote app was deployed, no GPU job or larger-model download was started, no business dataset was uploaded, and no charge was authorized. Actual provider auth, provider-side limit enforcement, CUDA compatibility/performance, GPU model quality, charges and future result import/deployment remain unverified.

The package manifest says training_performed=false/upload_performed=false, pins the exact base and source hashes, and keeps check targets/reference documents out of request.json. Prepared examples, credentials and local models remain outside Git.

## Subsequent real account connection

The founder created a Modal account and explicitly asked to connect it. The installed official SDK browser approval flow completed. Its token pair was transferred in memory to Own over loopback with proxies disabled, verified using the existing read-only AppList check, and saved using Windows DPAPI. No plaintext Modal profile was created and no keys were logged or exported. Fresh Own status confirmed connected=true, protected connection file present, remote_training_enabled=false. This establishes real authentication; L4 execution, available credits, provider billing limits and actual GPU charges remain unverified. No GPU job or business-data upload was started.

## Retained Step 2 evidence

# Step 2 verification — 2 November 2026

## Current automated evidence

- **46 Python tests pass** with `python -m unittest discover -s tests -q`. Covers the existing workbench plus permission and stale-confirmation rejection, immutable datasets, edit conflicts, scope, train/check separation, candidate review/selection, assistant-only labels, no silent truncation, Windows paths, artifact substitution, failed/cancelled/restarted workers, BPE tokenizer artifacts, baseline failure handling, adapter exports and trained inference routing.
- `node --check web/app.js` and `node --check web/training.js`: pass.
- **2 browser regressions pass** in `tests/browser/training-inputs.cjs`, each first observed failing: dirty instructions cannot enter an edit flow that replaces them; an old slow PATCH cannot close a replacement modal or erase its text. They use a separate temporary Own instance and fictional data.
- Design contract lint completed with exit code 0. Premium strict static audit still reports **10 actionless-button findings**, because it cannot follow delegated `data-action` handlers (six existing and four training findings). The audited controls have implemented handlers; relevant training/review/selection/export flows were exercised in the browser. The strict static audit does **not** pass.

## Actual training and portable serving

Used the laptop CPU, not a mocked provider. Isolated environment: PyTorch **2.9.1+cpu**, Transformers **4.57.6**, PEFT **0.18.1**, Accelerate **1.12.0**. Installation encountered Windows MAX_PATH; extended-length executable paths fixed it without changing Windows or global Python.

Base: `HuggingFaceTB/SmolLM2-135M-Instruct`, revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`. Base SHA-256: `5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c`.

Fictional workspace “Training demo · fictional”, job “Shop replies”: **6 teaching examples, 2 held-out checks, 48 real optimizer steps**. The successful run changed **460,800 adapter parameters** and saved a **1,858,776-byte safetensors adapter**. Training/reload/comparison took **72 seconds**, excluding setup. First/last teaching loss: **3.30496 / 0.01245**. Loss measures training fit, not accuracy.

The saved adapter was reloaded before comparison. Both sides used the same held-out requests, base revision, instructions and deterministic decoding, without teaching answers or reference passages.

| Fictional check | Untouched base | Reloaded trained adapter |
|---|---|---|
| How many days should I allow for delivery? | Reached its answer limit; no complete answer shown | “Standard delivery takes five working days.” |
| Is a receipt required for returns? | Incorrectly said no receipt was required | “Yes, returns require a receipt for a return.” |

Two demonstration cases do not establish broad quality. They demonstrate an actual weight update, fresh reload and changed held-out behavior.

Browser verification: create business/job, save instructions, add/edit examples, add checks, reject unchecked permission, start training, leave/reopen the view, stop a real worker, retry, inspect real progress, review comparison, select adapter, generate a real draft answer, download its ZIP, run existing checks with the adapter, approve a version, and generate a real approved answer. The approved delivery answer matched the fictional five-working-day policy. Desktop **1280×900** and narrow **390×844** were inspected; narrow document width **380** versus inner width **390**, no global horizontal overflow, no page JavaScript errors.

Extracted the download into a separate folder and ran its copied `trained_runner.py` with `--offline --base-dir`, outside the application directory. It returned **“Yes, returns require a receipt for a return.”** using the exported adapter, without an Own API call. The ZIP contains actual adapter weights, exact base identity/hash/license information, dataset/provenance/permission, config, separate checks and runner. Base weights are explicitly excluded. Teaching-only JSONL excludes held-out checks. No provider charge or business-data upload was made.

## Independent review and limits

A fresh read-only reviewer inspected the Step 2 branch. No critical lifecycle issues were found. Both important input-loss findings were reproduced and fixed with observed RED → GREEN browser tests, followed by the passing full Python suite. The reviewer independently ran 19 targeted training tests; its full-suite attempt stalled in its environment, while the implementer's full suite completed successfully.

Required documentation and stale “training comes later” version copy were updated. No deferred minor findings remain. Cloud GPUs, production tenant authentication/encryption, larger-model quality, automatic migrations and managed deployment remain outside this local milestone. Changing comparison reviews affects future selection; earlier approved versions remain immutable until explicitly switched.

## Historical Step 1 evidence

The following retains the earlier milestone's original verification counts.
# Milestone 1 verification — 2 November 2026

This is a local, single-owner development workbench. It is not the completed YC product or an enterprise release.

## Automated checks

- `python -m unittest discover -s tests -v`: **21 tests passed**. SQLite persistence, workspace scoping, source retrieval boundary, exact normalized teaching/check split separation, stale-edit rejection, snapshot-bound approvals, correction capture/refinement, repeated check recovery, 10-check limit, archive contents, rejected uploads, engine errors, actual-response parsing and cloud-model exclusion.
- `node --check web/app.js`: passed.
- Design configuration lint using `@google/design.md`: **0 errors, 8 warnings**. Warnings concern two unsupported `minHeight` metadata keys and six tokens unused by component metadata. CSS uses the documented tokens; the metadata is advisory and does not drive runtime styles.
- Premium UI strict static audit ran. It reports **six actionless-button findings**, all caused by its inability to follow this app's delegated `data-action` listener. These are the correction button, two check-review buttons, version switching, the roadmap and the connection button. Their actions are implemented in `web/app.js`; correction, positive review, switching, roadmap/connection have browser/runtime evidence, and negative review uses the same API with the `fail` value. The audit does not pass; do not present it as a clean audit. Initial empty-hash links were replaced with real home routes.

## Actual local model

Ollama was installed but had no models. Downloaded `qwen3:1.7b` from the official Ollama model library, approximately 1.36 GB on disk. An actual app request asked “How many days does standard delivery take?” against a fictional reference policy. The returned answer was “Standard delivery takes five working days.” Recorded model inference time: approximately **15.0 seconds** on the development laptop for that first request. This one example is not a quality benchmark.

Two actual held-out check runs asked whether an order could be returned after 20 days with a receipt. Both responses matched the fictional 30-day policy. Each was manually reviewed before approval. No fake model output or automatic correctness score was used.

## Browser checks

Tested through the app UI:
- Empty required-name validation and field focus.
- Creating the fictional sample business with a source policy and teaching example.
- Saving model choice and instructions.
- Real local inference, answer persistence and supplied reference disclosure.
- Natural-language correction saved to a separate teaching example.
- Adding a held-out check, truthful running state, real output and manual review.
- Approving version 1; editing instructions makes earlier checks visibly stale.
- Rerunning checks, approving version 2, and switching back to version 1.
- Workspace export confirmation and download action. Separately fetched and inspected the actual ZIP endpoint: valid archive, accurate manifest, teaching-only JSONL and `model_weights_included: false`.
- App restart using `python run.py --launch`; saved workspace, examples and version survived. A fresh browser tab reconnected after the server restart.
- Laptop layout at 1280×800 and narrow layout at 390×844. Narrow viewport measured `documentWidth: 380` versus `viewport: 390`; no page-wide horizontal overflow. Navigation remains horizontally scrollable where needed. Temporary viewport override reset afterward.
- A separate temporary QA server deliberately delayed PATCH by five seconds. Before the fix, the instruction field remained editable during save and its later edit was overwritten. After the fix, fields were disabled while the save was pending and restored on completion.

## Independent review and fixes

A separate read-only reviewer found three important issues and one setup issue. Addressed:
1. An 11th check could strand the job: reject it at creation without affecting the first ten. A regression test was observed failing and then passing.
2. Slow save could discard newer edits or repaint another job: lock form fields while saving and bind completion to the originating route/job.
3. Background polling could advance the version used by a stale form: the form retains its own rendered `data-revision` and submits that revision. Polling cannot silently update it.
4. Newly detected models could be missing from an already-open selector: update model options in place without replacing instructions.

Further checks fixed repeated corrections to the same request and excluded advertised remote/cloud models from the local choices. Both regressions were observed failing before their fixes, then passed in the whole suite.

No second independent review was performed after the fix pass. The author verified the fixes with tests and browser checks. Enterprise security, real model training, clean-machine installation, systematic accessibility certification and broad model quality were not claimed or verified.

## Delivery decisions and limits

Use the existing projectless workspace, without changing a shared Git repository. Use a buildless frontend and Python/SQLite to keep first setup light. The full YC scope remains in PRODUCT.md and the in-app roadmap, with training/deployment features explicitly marked as later stages. ZIP export is business data/configuration export, not trained-model ownership. Authentication, encryption, PDF/Word parsing, adapters, cloud GPU jobs and a standalone model runner remain future work.

The installed runtime was tested; SETUP.cmd is provided for a clean Python environment, but a clean-machine reinstall was not exercised. This local edition should be used with sample or non-sensitive information.

The main app is left running as a hidden `pythonw.exe` loopback server on port 8765. The temporary delayed-save QA server on port 8766 was stopped. Browser preview saved beside the project as `own-intelligence-preview.jpg`.
