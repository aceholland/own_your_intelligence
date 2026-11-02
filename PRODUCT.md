# Own — product and milestone contract

## Intent
Make company-owned intelligence usable by ordinary employees across industries. The user explicitly chose one platform, a shared base model with separate company customizations, the full YC improvement lifecycle, and plain-language interactions. They asked to start building on their Windows laptop, have 16 GB RAM and no dedicated training GPU, and previously asked us to proceed without a questionnaire.

## Milestone 1: local teaching and evaluation workbench
Ship a real local app: create workspaces and jobs, explain instructions, upload UTF-8 text/Markdown/CSV, add teaching examples, run a locally installed Ollama model with relevant source passages, correct answers, maintain separate check examples, run checks, manually review outputs, approve immutable versions, switch back to a version, and download a portable workspace archive plus training JSONL. No simulated model responses or fabricated quality scores.

Use the working name Own. No industry-specific schema. Default language English; use the browser's locale and timezone for display. Source references mean passages supplied to a model, not independently verified support for its answer. User review remains necessary.

## Architecture decisions (builder choices)
- Python 3.11+ / FastAPI / SQLite / buildless HTML, CSS and JavaScript. One process, loopback only, no frontend toolchain or Docker required. Installed Python and FastAPI make this smaller than the earlier tentative React/Postgres stack; those were proposals, not requirements.
- Ollama is the only inference provider in milestone 1. Support installed models and fail honestly if none is ready. Do not download models automatically or route company data externally.
- One local owner. Workspaces separate records and retrieval, but are NOT multi-user authorization. Production identity, tenant security, encrypted storage, audited on-prem packaging and cloud providers are later milestones. Data lives in the user's app directory; no analytics or external fonts.
- Training JSONL exports teaching examples only. Held-out checks never enter teaching prompts or training exports. Conflicting or duplicate inputs across splits are rejected.
- Store immutable version snapshots including model, instructions, examples and sources. Live runs use the approved snapshot. Draft changes require new checks and approval; reviewing one check is a workflow gate, not statistical proof of reliability.
- Final model upgrades are explicit. Changing document knowledge or instructions invalidates current draft check results. Model weight training is NOT implemented in this milestone; never label prompt/example changes as retraining.
- Protect loopback endpoints from cross-site mutation with origin/host validation and a session CSRF token. No arbitrary filesystem access, remote provider URLs, automatic tool execution, billing, or destructive deletion in milestone 1.

## Full YC feature sequence
1. Local workbench: workflow definitions, documents, expert examples, production runs, corrections, separate evaluations, approval/rollback, portable data exports.
2. Governed dataset builder and actual LoRA training: local CPU starter available with permission/provenance, explicit consent, job history and isolated adapters; larger-model GPU training remains next.
3. Controlled deployment and ownership: real model artifacts, licensed runner, reproducible serving, customer cloud and on-prem support.
4. Failure-driven improvement: diagnosis, compare deterministic/retrieval/prompt/training fixes, held-out evaluation and rollout monitoring.
5. Base-model migration and optional frontier routing: explicit policies and approvals, quality/cost comparisons, tested migration, private deployment boundaries.

## Approaches considered
Cloud SaaS first creates credential, cost and data-handling dependencies before the first local experiment. Full local training is unsuitable for this laptop. The selected local-workbench-first approach establishes the genuine data and evaluation lifecycle now and keeps GPU training an explicit later stage. It does not pretend that data export is model ownership.

## Acceptance
Persist across restart; workspace data never crosses retrieval/export boundaries; unsafe/oversized files fail clearly; no inference is fabricated; save corrections independently; no test leakage; reviewed evaluations bind to a specific snapshot; stale checks cannot approve a changed draft; switching versions restores actual snapshot behavior; export is self-describing and accurately lists missing model weights; interface works at laptop and phone widths with keyboard labels, visible focus and useful errors.

## Milestone 2: local weight training
The current user asked for actual per-business retraining and very simple controls. The implemented local starter shares a pinned SmolLM2-135M-Instruct base while keeping datasets and LoRA adapters separate by workspace/job. It records permission, freezes datasets, performs real assistant-only weight updates, reloads saved safetensors, compares against the untouched base, requires human review before draft selection, and retains the existing check/approval/version flow. A baseline generation failure is a visible before-training outcome; successful candidate answers still run and require review. Candidate failures block selection. A private model export includes an independent runner and exact base revision/license/checksum, with base weights obtained separately.

Full-weight training of the original 1.7B model is still a poor CPU default on this laptop. Small adapter training is feasible and proves the lifecycle. This builder choice avoids paid GPU dependencies now; it does not claim frontier-model quality or complete the cloud, security and deployment roadmap.
