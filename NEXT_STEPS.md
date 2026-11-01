# Next session — Step 2

Planned for **3 November 2026**, at the founder's request. No scheduled automation or paid training job has been created.

## Current checkpoint

Step 1 is a working local teaching and evaluation workbench. It supports general business jobs, separate workspaces, local Ollama responses, source notes, teaching examples, corrections, held-out checks, human review, approved configuration versions, switching versions and a workspace/data export.

The full product direction remains in [PRODUCT.md](PRODUCT.md). Setup is in [README.md](README.md). Test results and limitations are recorded in [VERIFICATION.md](VERIFICATION.md).

## Step 2: begin actual model specialization

Start with a governed dataset builder, then connect real adapter training. Keep normal users in a simple flow: **Review examples → Check permission → See estimated cost → Approve training → Compare results → Choose whether to use the update.**

1. Add example editing and review so users can fix their teaching data without recreating a job.
2. Record dataset provenance, permission to train, and a frozen dataset version. Keep check examples separate and detect overlap.
3. Define the training-provider boundary, job states, credentials and explicit spending approval. Use rented GPU infrastructure for actual LoRA training; this laptop remains the development and control machine.
4. Implement a real training job and retain the resulting adapter, its base-model identity/license information, dataset version and training configuration.
5. Evaluate the candidate against the unchanged held-out checks and current baseline. Explain results in everyday language. A completed training job does not automatically mean a better model.
6. Add explicit deployment approval and verify that exported trained artifacts can be loaded independently on supported infrastructure.

Work through these in small verified milestones. Do not show training progress without a real job, label prompt changes as retraining, or make paid calls without an explicit budget. Authentication, encryption, broader file support and deployment hardening remain necessary before real customer data or production use.

## Begin here

Open START.cmd, inspect the current app and run:

```text
python -m unittest discover -s tests -v
node --check web/app.js
```

Then review the dataset-builder scope before changing the product. The current UI and tests are the starting point; do not replace the working app with a new scaffold.
