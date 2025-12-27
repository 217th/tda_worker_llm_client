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

Timeouts (MVP recommendation):
- Cloud Function timeout: `780s` (13 minutes)
- Gemini request deadline: `600s` (10 minutes)
- Reserve `120s` for cleanup/finalize (GCS write + Firestore patch). See `spec/implementation_contract.md`.

Service account must have (minimum):
- Firestore read/write access to `flow_runs/*` and prompt/model collections
- Cloud Storage object write access to artifacts bucket
- MVP (AI Studio): no special IAM for Gemini invocation (uses API key). Service account should have access to Secret Manager to read the API key.
- (future, non-MVP) Vertex AI: Gemini invoke permissions via IAM (e.g., appropriate Vertex AI roles) when switching to ADC/IAM auth.

Configuration via environment variables (draft):
- `GCP_PROJECT`
- `GCP_REGION`
- `FIRESTORE_DATABASE` (default `(default)`)
- `FLOW_RUNS_COLLECTION` (default `flow_runs`)
- `LLM_PROMPTS_COLLECTION` (default `llm_prompts`)
- `LLM_MODELS_COLLECTION` (default `llm_models`)
- `ARTIFACTS_BUCKET`
- `ARTIFACTS_PREFIX` (optional)
- `GEMINI_API_KEY` (MVP, AI Studio; prefer injecting from Secret Manager)
- `GEMINI_LOCATION` (future/Vertex; if applicable)
- `GEMINI_TIMEOUT_SECONDS` (MVP, default `600`)
- `FINALIZE_BUDGET_SECONDS` (MVP, default `120`)
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
- MVP uses an API key for AI Studio. Store it in Secret Manager and inject into the function as an environment variable (do not commit it, do not log it).

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
