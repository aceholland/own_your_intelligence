# Business training implementation plan

> For agentic workers: execute with superpowers:executing-plans, using test-driven-development and one independent whole-branch review.

**Goal:** Actual per-business model training, comparison, serving and export in a simple local workflow.
**Architecture:** Frozen SQLite datasets, a supervised subprocess runtime, pinned shared SmolLM2 base with separate PEFT LoRA adapters, and existing approval/version gates.
**Tech stack:** Python/FastAPI/SQLite, PyTorch CPU, Transformers 4.57.6, PEFT 0.18.1, buildless JavaScript/CSS.
**Spec:** ../specs/2026-11-02-business-training-design.md

## Global constraints

- Windows Python 3.13 / 16 GB RAM / CPU; no paid provider calls or business data uploads.
- Base revision 12fd25f77366fa6b3b4b768ec3050bf629380bac; safetensors only, remote code disabled.
- Keep existing workspaces, inference, immutable versions and simple shared UI primitives.
- At least 3 teaching examples and 1 held-out check; no silent token truncation or invented quality claims.
- Data/artifacts/dependency environments remain ignored under data/.

## Review focus

- Editing examples after confirmation cannot silently train a different dataset.
- Cross-business model IDs, artifact substitution and unfinished checkpoints must fail closed.
- Cancellation/restart must not label partial training successful or leave a busy lock permanently held.
- Editing or navigating during polling must preserve unsaved input and avoid stale responses.
- Comparisons must use the exact same base revision, held-out inputs and decoding without teaching leakage.

### Task 1: frozen datasets and training lifecycle

Files: own/training_data.py, own/training_store.py, own/store.py, tests/test_training_store.py.
Interfaces: TrainingRepository(store).prepare(ws,job); begin(ws,job,dataset_hash,permission); get/list/update; comparison review; select. training_data provides canonical dataset/fingerprint and message builders.

- [x] Add failing tests for permission, stale confirmation, immutable dataset, split leakage, edit conflicts, workspace isolation, failed/stale/unreviewed selection.
- [x] Run new tests and observe failures; implement minimal repository and example editing.
- [x] Run store tests and existing suite; commit independently.

### Task 2: real isolated training runtime

Files: own/training_runtime.py, own/training_worker.py, own/training_setup.py, requirements-training.txt, trained_runner.py, tests/test_training_runtime.py.
Interfaces: TrainingManager(store,data_dir,inference_lock) exposes status/setup/start/cancel/chat/export/close; worker train/answer reads a fixed task JSON and writes atomic progress/result files; setup installs pinned packages and downloads fixed base.

- [x] Add failing tests for assistant label masking/no truncation, artifact integrity, cancelled/failed worker reconciliation and honest export.
- [x] Implement real CPU LoRA loop, finite/changed weight checks, fresh reload comparison, progress, process supervision, bounded operations and cancellation.
- [x] Install isolated runtime; train fictional examples; load adapter in another process and run exported runner.
- [x] Run targeted tests plus complete suite; commit.

### Task 3: API integration and versioned inference

Files: own/api.py, tests/test_training_api.py, tests/test_api.py.
Interfaces: GET training/runtime; POST setup; GET job/training-plan; POST job/train; GET job/trainings; POST training cancel/review/select; GET training/export. Existing try/checks resolve scoped own:<training-id> models.

- [x] Add failing tests for real feature availability, boundary/consent/cross-workspace requests, selected adapter inference and export.
- [x] Wire service, scope validation, lifespan shutdown and useful errors; preserve original Ollama path.
- [x] Run all tests and JS syntax; commit.

### Task 4: simple training UI and end-to-end verification

Files: web/app.js, web/training.js, web/styles.css, DESIGN.md, UX-CONTRACT.md, README.md, VERIFICATION.md, NEXT_STEPS.md.
Interfaces: reusable Train it rendering/actions integrated with existing formAction/api/modal/polling and model choices.

- [x] Implement example editing and Review → Train → Compare screen using existing UI owners, visible real progress and persistent failures.
- [x] Verify setup/training/cancel/retry/comparison/selection/check/approval/export in browser, at laptop and narrow widths; preserve edits during polling.
- [x] Run final suite, syntax/static audit, actual-model/export evidence, and fresh independent review; fix important findings with regression tests.
- [x] Update user docs and commit final changes. Leave the working app running and report local URL and concrete limitations.
