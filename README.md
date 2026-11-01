# Own — your local business AI workbench

Step 1 of a platform for company-owned intelligence. Made for ordinary employees: describe a job, show examples, try it, correct it, check new cases, approve a version, and keep your data.

![Own local teaching and evaluation workbench](docs/preview.jpg)

The next session starts with [Step 2: actual model specialization](NEXT_STEPS.md). This repository contains application source and documentation; local business data, credentials and downloaded models are excluded.

## Open it

1. Double-click **START.cmd** in this folder.
2. Own opens at **http://127.0.0.1:8765** in your browser.
3. Choose **Explore a sample business**, or enter your business name.

Python and the app dependencies were already available on the development laptop. On another machine, install Python 3.11 or later, then run **SETUP.cmd** once. Setup creates a local `.venv` and installs the requirements from PyPI. Keep this whole folder together.

## Try real AI

Open Ollama. In Own, select **AI connection**. If a model is missing, run **INSTALL LOCAL MODEL.cmd** once; the suggested `qwen3:1.7b` model downloads about 1.4 GB. Business requests use the local Ollama service at `127.0.0.1:11434`; the app has no paid API integration. You may choose another installed local model.

1. Open a job and select **Teach it**.
2. Choose the installed model, explain the job, and save instructions.
3. Add a good teaching example and business reference notes if useful.
4. Select **Try it**, type a short request, and choose **Try my AI**.
5. Read the actual answer. **Fix this answer** saves your preferred answer as a teaching example in the draft.
6. In **Check it**, add a different request and the answer you expect. Run checks and review each actual answer.
7. In **Versions**, approve the checked draft. Try the approved version, or return to an earlier approved version later.

The sample business uses fictional shop policies. Example request: “How many days does standard delivery take?” Expected policy: five working days. A separate check could ask “What is the return window?” Expected: 30 days from delivery, with a receipt. These are demonstrations, not actual business policies.

## What works now

- Multiple local workspaces and general-purpose jobs.
- Persistent SQLite storage; no account needed.
- Instructions, teaching examples and corrections.
- UTF-8 `.txt`, `.md` and `.csv` source files, or pasted reference notes.
- Real locally installed Ollama model responses.
- Bounded keyword retrieval with visible supplied passages.
- Separate check examples, background check runs and manual review.
- Immutable approved configuration snapshots, explicit approval and switching versions.
- ZIP data/configuration export including teaching-only training JSONL and separately held-out checks.

## Full YC scope and the next stages

The system is industry-independent. `PRODUCT.md` records the complete direction and architecture.

| YC capability | This edition | Next implementation |
|---|---|---|
| Workflows become evaluations | Jobs and separate check examples; human reviews | Rich rubrics, metrics, independent datasets and larger evaluation batches |
| Expertise becomes training data | Teaching examples and correction JSONL | Consent/provenance review and dataset curation |
| Improve company-owned models | Prompt/example customization only | Actual isolated LoRA training jobs and trained artifact registry |
| Production failures drive improvement | Persisted answers and manual corrections | Failure diagnosis, fix comparison and rollout monitoring |
| Control changes | Approved configuration snapshots and rollback | Deployment approvals, canary releases and trained-model rollback |
| Run where the customer chooses | Local workbench and local inference | Reproducible customer-cloud and on-prem runner |
| Retain ownership | Portable business data and configuration | Licensed model artifacts and independently tested serving package |
| Carry learning to new base models | Explicit model choice and saved examples | Retrain/evaluate/migrate with compatibility checks |
| Optional frontier intelligence | No external provider calls | Explicit provider policies, credentials and spending approval |

Training model weights, trained adapter export, automatic migration, external tool actions, PDF/Word parsing, billing and production multi-user security are **not implemented**. Data export is not a trained model. A small local model is a development tool, not evidence that every business task can be automated reliably.

## Data and privacy

Data lives in `data/own.sqlite3` beside this README. Back it up with the app stopped, or use the workspace ZIP export for a portable copy. The app binds only to `127.0.0.1`; do not expose it to the internet. Workspaces separate records and retrieval within one owner's app. They are not production authentication or authorization boundaries.

There is no encryption or access control between people using the same Windows account. Use sample or non-sensitive data while production security is developed. No analytics, remote fonts or paid API calls are built in. The app does not execute instructions as tools or send email. Supplied source passages are not automatically verified citations.

Exports include business data; keep them private. Training JSONL excludes held-out checks. Exported model names still require obtaining the original model under its applicable license; model weights are not inside the archive. No export import flow is included yet.

## Limits and recovery

- 30 workspaces, 100 jobs per workspace, 40 files per workspace.
- UTF-8 files up to 1 MB and 200,000 characters each. PDFs and Word files are rejected with guidance.
- 200 examples per job; up to 10 checks in a local check run.
- Recent 20 answers and 10 evaluation runs displayed/exported per job, plus all examples, files and approved versions. The database retains older records.
- One model request at a time. A model response may take up to three minutes; keep tasks short.
- At most three matching text passages and two teaching examples enter a request. This is keyword retrieval, not semantic search.
- Changing a job, teaching example, source file or check example requires fresh checks before approving. The draft does not overwrite an approved version.
- If Own stops, reopen START.cmd. If Ollama stops, open it and check the connection. A browser refresh reconnects a changed local session.

For a visible terminal server, run `python run.py --no-browser`. Press Ctrl+C to stop it. START.cmd normally runs the server in the background; its errors are written to `data/server.log`. Closing the browser does not stop that background server. Restart Windows or stop the specific `pythonw.exe run.py` process in Task Manager when you need to stop it. A dedicated app shutdown control is a future convenience feature.

## Developer checks

Install test tooling with `python -m pip install -r requirements-dev.txt` if needed, then:

```text
python -m unittest discover -s tests -v
node --check web/app.js
```

Tests use temporary SQLite databases and a controlled model transport. They do not download models, spend money or establish real-model quality. Actual model availability and browser checks are recorded separately in `VERIFICATION.md`.

## Technical references

- [Ollama chat API](https://docs.ollama.com/api/chat)
- [Ollama installed model API](https://docs.ollama.com/api/tags)
- [Suggested small model](https://ollama.com/library/qwen3:1.7b)
- [Original YC request](https://www.ycombinator.com/rfs)
