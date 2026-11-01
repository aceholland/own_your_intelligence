# Local workbench implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task. The user already requested execution in this chat and opted out of further discovery questions.

**Goal:** A working, easy local teaching and evaluation app with real Ollama inference and persistent records.
**Architecture:** FastAPI serves static UI and a same-origin JSON API; SQLite records immutable versions and checks. Ollama is a fixed loopback inference adapter.
**Tech stack:** Python, FastAPI, SQLite, native ES modules and CSS.
**Spec:** ../../../PRODUCT.md

## Global constraints
Loopback only; no paid calls or automatic downloads; English plain-language copy; no fabricated inference, model training or evaluation scores; exclude checks from training; data is stored locally without encryption; single-owner development app.

## Review focus
- A stale check or a model error must not approve a changed version.
- Documents and examples from another workspace must never enter a prompt or archive.
- Long inputs, malformed files and missing Ollama need actionable errors and preserved form text.
- Overlapping teaching/check inputs invalidate evaluation independence.
- Cross-site mutation, stored markup and path traversal must not reach protected behavior.

### Task 1: Durable domain lifecycle
Files: `own/store.py`, `own/retrieval.py`, `tests/test_store.py`.
Interfaces: `Store(path)`, workspace/task/source/example CRUD, snapshot, run recording, check reviews, approve/activate/export.
- [x] Write behavioral tests for persistence, isolation, split separation, snapshot invalidation, correction and export.
- [x] Run `python -m unittest discover -s tests -v`; observe missing functionality.
- [x] Implement SQLite transactions and immutable snapshots; run the suite.

### Task 2: Actual model and API boundary
Files: `own/engine.py`, `own/api.py`, `run.py`, `tests/test_api.py`, `tests/test_engine.py`.
Interfaces: `create_app(data_dir, engine)`, `/api/*`, fixed Ollama `/api/tags` and `/api/chat`, bounded relevant passages.
- [x] Write failing API tests for request validation, CSRF/origin, workspace scoping, unavailable engine, failed checks and response recording.
- [x] Implement real inference and safe upload/export endpoints; run the entire suite.

### Task 3: Ordinary-user interface and launcher
Files: `web/index.html`, `web/app.js`, `web/styles.css`, `START.cmd`, `SETUP.cmd`, `README.md`, `DESIGN.md`, `UX-CONTRACT.md`.
- [x] Implement a consistent create → teach → try → check → version flow, shared modal/toast/form primitives, separate workspace library, setup recovery and honest roadmap.
- [x] Run JavaScript syntax validation and a real browser flow including errors, persisted reload, corrections, checks, version approval and narrow-width layout.
- [x] Add desktop launch/setup instructions, full feature roadmap and verification evidence.

### Final validation
- [x] Run the full Python suite, JS syntax check and premium static audit. Audit limitations are recorded in VERIFICATION.md; no claim of a clean static audit.
- [x] Fresh independent code review, fix material findings and rerun relevant checks.
- [x] Leave a working local launcher and accurately report actual AI/model availability and future features.

## Execution record
Projectless empty directory: use the current workspace, no worktree or shared repository mutations. Plan and source are user-facing outputs. Formal shell task-ledger helpers assume a Git checkout; record evidence here instead.
