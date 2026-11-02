# GPU training workflow plan

Execute inline using executing-plans, TDD, verification-before-completion and one independent whole-branch review.
Spec: ../specs/2026-11-02-gpu-training-design.md

Global constraints: free credits only; owner-confirmed provider $0 net spend limit/available credits before compute; no expected check targets/reference documents uploaded; no credentials in files/responses/logs; preserve local training; no GPU serving selection until supported deployment is verified.

Review focus: a connection/estimate is not billing approval; lost workers cannot claim cancellation/success; result archive contents cannot escape scope or execute code; results match the exact frozen input/base/source; polling and late responses preserve new forms.

### 1. Job state and validated results
Files: own/gpu_jobs.py, own/gpu_result.py, tests/test_gpu_jobs.py, tests/test_gpu_result.py.
- [x] Add failing free-only/consent/scope/staleness/one-active-state tests and hostile/fake result fixtures.
- [x] Implement repository and bounded verifier; 10 targeted tests passed before committing.

### 2. Real provider bridge and progress
Files: own/gpu_worker.py, own/gpu_jobs.py, gpu/train_on_gpu.py, gpu/training_core.py, tests/test_gpu_worker.py.
- [x] Test worker exit/cancellation/secret boundaries without remote work.
- [x] Implement actual ephemeral SDK call/queue, region, measured progress and protected credentials; real SDK definitions validate without launch. Actual CPU core result also passed the new verifier.

### 3. API and simple review/download flow
Files: own/api.py, web/gpu.js, web/app.js, tests/test_gpu_api.py, tests/browser/gpu-run.cjs.
- [x] Add failing API gate/scope/result-download tests; wire supervised lifecycle and UI.
- [x] Verify free-only form gates, progress/error recovery, comparison/review, download and 390px layout with controlled provider fixtures. 87 Python tests and JavaScript syntax pass before review.

### 4. Independent review and first-run handoff
Files: README.md, NEXT_STEPS.md, VERIFICATION.md, DESIGN.md, UX-CONTRACT.md.
- [ ] Obtain read-only review; reproduce/fix important findings and run final checks.
- [ ] If owner-confirmed billing conditions are available, run the exact fictional test and validate its real saved result/reload; otherwise leave the actual GPU test pending without starting compute.
- [ ] Record concrete evidence/limits, leave app running and commit.
