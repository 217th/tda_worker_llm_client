# Deploy and environments

## Environments

Recommended environments:
- `dev` (fast iteration, permissive logs, smaller quotas)
- `staging` (prod-like config, smaller scale)
- `prod`

Environment differences (minimum):
- GCP project ID
- Firestore database (or namespace via collection prefixes)
- GCS bucket name(s) for artifacts
- allowed Gemini models (allowlist)
- logging verbosity / sampling

## Deployment model

Target runtime: **Google Cloud Functions (gen2)** with an **Eventarc Firestore trigger**:
- event type: Firestore document update
- document: `flow_runs/{runId}`
- region: same as Firestore / Eventarc routing policy (decision TBD)

Service account must have (minimum):
- Firestore read/write access to `flow_runs/*` and prompt/model collections
- Cloud Storage object write access to artifacts bucket
- Gemini/Vertex AI invoke permissions (e.g., `aiplatform.endpoints.predict` / model invocation role depending on SDK)

Configuration via environment variables (draft):
- `GCP_PROJECT`
- `GCP_REGION`
- `FIRESTORE_DATABASE` (default `(default)`)
- `FLOW_RUNS_COLLECTION` (default `flow_runs`)
- `LLM_PROMPTS_COLLECTION` (default `llm_prompts`)
- `LLM_MODELS_COLLECTION` (default `llm_models`)
- `ARTIFACTS_BUCKET`
- `ARTIFACTS_PREFIX` (optional)
- `GEMINI_LOCATION` (if applicable)
- `LOG_LEVEL`

Environment variable style (implementation guidance):
- use `UPPERCASE_WITH_UNDERSCORES`
- prefer a project prefix when config becomes shared across multiple workers (e.g., `TDA_LLM_...`) (decision TBD)
- group related variables (Firestore, GCS, LLM, logging)

Validation rules (minimum):
- `ARTIFACTS_BUCKET` must be non-empty and refer to an existing bucket in the same project/environment
- `FLOW_RUNS_COLLECTION` must be non-empty (default `flow_runs`)
- collection names must not contain `/`
- `LOG_LEVEL` must be one of `DEBUG|INFO|WARNING|ERROR`

Secrets:
- Prefer Workload Identity / service account auth; avoid embedding API keys.

## Rollback plan

- Roll back to a previous function revision (gen2 supports revisions).
- If a deployment introduces incorrect prompt/model behavior, rollback can be done by:
  - reverting prompt/model docs version (if versioned via IDs)
  - rolling back function revision

Smoke checks (draft):
- Update a `flow_runs/{runId}` document to include one `READY` `LLM_REPORT` step with satisfied `dependsOn`
- Confirm:
  - logs show `step.claim.succeeded`
  - artifact exists in GCS at expected path
  - Firestore step status transitions to `SUCCEEDED` and `outputs.gcs_uri` is populated
