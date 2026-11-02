# Step 2: real training that a business owner can use

## Intent and constraints

Build on the working local app. A business owner reviews examples, confirms permission, presses Train my AI, compares actual answers, and decides whether to use the result. All businesses share one pinned open base model; each job gets an isolated LoRA adapter and frozen dataset. An adapter changes model weights; adding examples to a prompt does not.

The founder has authorized implementation and sensible defaults, and previously opted out of extended discovery. This design records implementation choices, rather than creating another approval gate. No paid services or credentials are needed for this milestone.

## Approaches considered

- Cloud GPU first: supports stronger models but requires an account, credentials, a spending limit, and approved data transfer. Keep for a later provider implementation.
- Train the existing 1.7B Ollama model directly: Ollama is an inference runtime; CPU training its unquantized source is a poor default on this 16 GB laptop.
- **Chosen: free local starter training.** Use the official HuggingFaceTB/SmolLM2-135M-Instruct base, immutable revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`, Apache-2.0. Train real PEFT LoRA weights on CPU, save safetensors, compare against the identical untouched base, and load the adapter for real requests. This small English model proves the complete training lifecycle; it is not a replacement for a powerful production model.

## User flow

Keep Teach it / Try it / Check it / Versions; insert Train it after Teach it. Reuse existing fields, modal, buttons, toast, errors and responsive layout. Train it has three recognizable stages: Review examples, Train, Compare. Technical settings have safe defaults and live under a disclosure.

1. Edit teaching/check examples with conflict protection and provenance. At least three teaching examples and one separate check are required. Recommend substantially more varied examples before relying on results.
2. One-time Setup local training downloads pinned Python packages and the public base model. Show real named stages, retry, and errors; never a fake download percentage. No business information is uploaded.
3. Training confirmation names the business, example/check counts, local execution, zero provider charge, and data permission. A request freezes data and records consent, provenance and hashes. Reject stale confirmation, duplicates across splits and concurrent operations.
4. Real training runs in an isolated subprocess with a bounded CPU/memory profile, assistant-only loss, no silent truncation, deterministic seed, actual step progress, finite loss checks, cancellation and restart recovery. Only success with changed adapter tensors and a reloadable checkpoint is a completed job.
5. Generate before/after answers to the frozen held-out checks using the same untouched base and trained adapter, same instructions and decoding. Neither teaching examples nor reference notes are supplied in this comparison. Report output and manual review; training loss is never presented as accuracy. Candidate errors block promotion. A baseline failure is shown as an observed before-training outcome; still generate and review the candidate independently.
6. After every candidate answer is reviewed Looks right, Use this training selects its immutable model in the draft. It requires the current dataset fingerprint to match. Existing Check it / Approve version still gates live use. Earlier approved versions remain usable.
7. Download trained model exports the adapter, exact base identity/revision/license, tokenization, dataset/provenance, consent, training config and comparison in a ZIP, plus a standalone runner. Base weights are explicitly excluded and downloaded separately once. No arbitrary executable model code or pickled weights.

## Architecture

Use the existing SQLite records and scope checks, with a focused training repository. Job status and datasets persist independently of browser tabs. A manager owns one active subprocess on this laptop, shares the inference lock, supervises completion/cancellation, and reads actual progress. Install an isolated `data/training/runtime` environment; keep caches, logs, models and artifacts under ignored `data/`. Never modify global Python packages. Worker processes use only allowlisted operations and a fixed model revision, disable telemetry and remote code, and use offline model loading after setup.

Use a canonical dataset hash independent of the selected inference model, while retaining all data/instructions/source/check content and provenance. Mutation conflict tokens cover example edits and training confirmation. Artifacts are scoped to workspace/job/training IDs, with recorded SHA-256 checks verified before serving or export. Comparison and serving load exact saved adapters. Only completed, reviewed matching datasets can be selected. Restart interrupts unfinished work and cannot promote partial output.

## Scope and evidence

Deliver real CPU retraining, adapter serving/export, frozen train/check separation, human comparison and existing approval/rollback. Keep the original Ollama workflow. Cloud GPU billing, multi-user security, encryption, arbitrary models, production guarantees and automatic base migration remain outside this milestone. Exercise a real download, training, fresh-process reload, comparison and standalone exported runner using fictional sample data. Unit/API tests use controlled workers for failure and isolation boundaries, with real-model evidence documented separately.

Sources: [model card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct), [PEFT checkpoint format](https://huggingface.co/docs/peft/developer_guides/checkpoint), [LoRA](https://arxiv.org/abs/2106.09685).
