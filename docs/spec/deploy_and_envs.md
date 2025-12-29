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
- region: must match the Firestore database location; Eventarc trigger location must be the same region as the function

Region alignment rule (MVP): Firestore DB location, Eventarc trigger location, and function region must be identical.
If they differ, stop and create/select a Firestore DB in the target region before deploying.

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
- `GEMINI_API_KEY` (optional; MVP/AI Studio; prefer injecting from Secret Manager; single-key mode)
- `GEMINI_API_KEYS_JSON` (optional; MVP/AI Studio; prefer injecting from Secret Manager; multi-key mode)
- `GEMINI_API_KEY_ID` (optional; required when `GEMINI_API_KEYS_JSON` is used; selects active key by id)
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

### Gemini API key management (MVP / AI Studio)

Goal: (1) keep the API key out of code/commits, (2) support safe rotation, (3) guarantee the key is never emitted in logs or persisted artifacts.

#### Recommended secret shape (rotation-friendly): `GEMINI_API_KEYS_JSON`

Store a single Secret Manager secret whose value is a JSON array (string) of keys:

```json
[
  { "id": "primary_v1", "apiKey": "AIza..." },
  { "id": "primary_v2", "apiKey": "AIza..." }
]
```

Runtime selection:
- if `GEMINI_API_KEY` is set: use it (simple single-key mode; mainly for local dev)
- else: require `GEMINI_API_KEYS_JSON` and require `GEMINI_API_KEY_ID` to select the active key by `id`

Validation rules (implementation guidance; strict, “by analogy” with other workers):
- `GEMINI_API_KEYS_JSON` must be a valid JSON array of objects with non-empty `id` and `apiKey`
- no duplicate `id`
- `GEMINI_API_KEY_ID` must exist in the array
- do not include the key (or its hash) in error messages/logs

#### Deployment: Secret Manager → env var injection (Cloud Functions gen2)

Inject secrets via deployment config, not via committed files.

Example (illustrative; exact flags may vary by environment):
- set secret env var: `GEMINI_API_KEYS_JSON` from Secret Manager (`:latest` or pinned version)
- set non-secret env var: `GEMINI_API_KEY_ID=primary_v2`

#### Rotation runbook (MVP)

1) Create a new API key in the provider console (AI Studio).
2) Add a new Secret Manager version updating `GEMINI_API_KEYS_JSON` to include the new key (new `id`).
3) Redeploy / roll a new revision so new instances read the updated secret at startup (no hot-reload is assumed).
4) Switch `GEMINI_API_KEY_ID` to the new `id` (canary in `dev`/`staging` first).
5) After verification, remove/disable the old key (rotate by updating the secret again).

Notes:
- Treat “rotation” as a controlled rollout: the worker should log only `llm.auth.keyId` (not the key) so you can correlate which key was active during incidents.
- Never persist the API key (or derived values) into Firestore step outputs or GCS artifacts.

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
