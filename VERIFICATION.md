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
