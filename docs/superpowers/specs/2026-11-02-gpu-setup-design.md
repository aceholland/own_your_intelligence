# Step 3: stronger-model setup

The founder asked for the next step, then explicitly chose **no cloud account yet; build setup first**. Deliver the account/setup and frozen-package workflow now. Do not start a remote app, build a cloud image, upload business information or spend money. Keep local training working. No terminal commands are part of the ordinary-user flow.

## Choice and user flow

Use Modal as the first provider: ephemeral per-job GPU functions, an official Python SDK and provider-side spend limits. A generic GPU-server integration creates more infrastructure work; notebook-only training creates more manual steps. These remain alternatives, not parallel implementations.

Train it links to **Set up a stronger model**. Three plain-language steps: create a Modal account, set a provider spending limit, connect its token pair. Links open the provider's own pages. SDK installation is a separate explicit local action, free of compute/data-transfer side effects. Connection checks list apps read-only, never deploy or run one. Mask credentials, provide accessible reveal controls, never return them or store them in browser storage. On Windows, save verified credentials using user-scoped DPAPI under ignored data/gpu; unsupported platforms keep them in process memory only. Disconnect removes the saved token pair without changing the provider account.

The same page prepares a private GPU training ZIP per job. Preparation does not require a connected account or upload. It freezes the dataset, exact Qwen3-4B-Instruct-2507 revision, adapter config and planning allowance, records permission, and rejects a stale hash. The package contains a real Modal training entrypoint, independent GPU runner, exact dependencies and manifest. Only teaching examples, instructions and held-out requests are eligible for future upload; held-out target answers and reference documents remain local. It contains no credentials and no base weights. It is marked training_performed=false. Package history is scoped and immutable.

Model: Qwen/Qwen3-4B-Instruct-2507, revision cdbee75f17c01a7cc42f958dc650907174af0554, Apache-2.0. L4 preset, one container, no retries, bounded execution. Use pinned Transformers/PEFT and real BF16 LoRA with assistant-only loss, changed-weight checks, reload, matching baseline/candidate checks and safetensors. The portable entrypoint refuses launch without separate explicit launch/data-transfer/billing approval and a provider-spend-limit acknowledgement. No remote launch endpoint is exposed by Own in this setup-only milestone. Future integration must validate actual GPU results before selection or serving; preparation is never presented as trained intelligence.

Planning allowance is not a hard invoice cap. Quote GPU+requested CPU/memory rates from the current official pricing snapshot, exclude extras explicitly, and link provider billing controls. No charge is authorized by preparing a file or connecting an account.

## Verification

Unit/API tests cover secret redaction, real DPAPI roundtrip, read-only authentication command, SDK errors, stale data, permission, scoping, no expected-check-answer leakage in the upload payload, safe private ZIPs and absence of compute calls. Verify the Modal SDK/entrypoint locally without an account. Browser-check setup, mask/reveal, errors, private preparation/download, existing local training, and narrow layout. Real provider authentication and L4 training remain explicitly unverified until the founder creates an account and approves a run.

Sources: https://modal.com/docs/guide/apps ; https://modal.com/docs/guide/budgets ; https://modal.com/pricing ; https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507 ; https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
