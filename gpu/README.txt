Own GPU training preparation

This private package has NOT trained a model or uploaded business information.
request.json freezes teaching data, job instructions and held-out requests.
local-checks.json contains expected answers and stays on your laptop.
No reference documents, expected check answers or credentials are sent by the trainer.

The first supported target is Modal L4 with a pinned Qwen3 4B Instruct base.
The training entrypoint contains real CUDA LoRA optimization, saved-weight checks,
fresh reload and before/after comparison. An actual L4 run has not been verified
in the setup-only milestone. Own has no remote-launch or result-import endpoint yet.

Before running: create the account, set its provider-side spending limit, and
separately approve the charge and data transfer. The package's planning allowance
is NOT a hard invoice cap. Image preparation, storage, network and taxes may add
cost. Check current prices: https://modal.com/pricing
Spending limits: https://modal.com/docs/guide/budgets

Developer launch after those approvals, from this extracted folder:
python -m pip install modal==1.6.3
python -m modal token new
python train_on_gpu.py --package . --approve-spend --approve-upload --provider-spend-limit-set

The function uses one GPU, no retries and a bounded timeout; it is ephemeral.
Model weights are never returned until real training and saved-adapter reload finish.
Result ZIP contains adapter/ and manifest.json with the actual comparison and hashes.
Keep local-checks.json alongside the result for human review; no automatic quality score.
Deployment/selection into Own is a later verified integration, not implied by preparation.
An independent CUDA runner is provided as run_model.py with training_core.py.
Both need the GPU model requirements; the base weights are obtained separately once.
