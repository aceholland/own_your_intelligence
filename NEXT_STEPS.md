# Next steps after local model training

## Current checkpoint

Step 2 has actual per-business/job CPU LoRA training, isolated adapters, frozen reviewed datasets, permission/provenance, real progress, cancellation/restart recovery, fresh-checkpoint comparisons, human selection, versioned serving and a model export with an independent runner. The existing Ollama workflow still works. See README.md for the user flow and VERIFICATION.md for evidence.

Open **START.cmd → your job → Train it**. The training engine and small shared base are installed on this laptop. “Training demo · fictional” contains the verified example; its approved version uses a real trained adapter. New businesses start with their own empty datasets and models.

This is a small English local starter. Use varied teaching examples and independent checks; measure quality before deciding whether training helped. Business data and weights stay outside Git under data/.

## Next milestone: stronger models and supported deployment

1. Add a real GPU provider behind the existing frozen-dataset/job boundary. Choose the provider, model, data location and explicit spending limit before any paid run. Never silently upload examples or start charges.
2. Compare larger candidates against the same frozen held-out checks; retain exact base identity, data version, config, artifacts and license information.
3. Extend the tested independent runner into supported customer-cloud/on-prem packaging, with reproducible environments and controlled deployment/rollback.
4. Add production identity, tenant authorization, encryption, auditing and deletion before real customer or regulated data.
5. Continue the YC lifecycle: failure diagnosis, measured fix comparisons, rollout monitoring, base-model migration and optional frontier routing with explicit policies.

No GPU account, paid provider job, billing integration or scheduled automation is configured. Keep the working local app and its verified training lifecycle as the starting point.
