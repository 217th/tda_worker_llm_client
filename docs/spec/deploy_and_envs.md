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

SDK/endpoint selection (MVP):
- Use the Google GenAI Python SDK for Gemini requests.
- AI Studio (Gemini Developer API): API key auth; pass the key explicitly (do not rely on SDK env defaults).
- Vertex AI (future): same SDK with `vertexai=True` plus explicit project and location.
- Structured output (`application/json` + JSON Schema) and image inputs are supported by the SDK; validate
  the combined multimodal + response schema path in Epic 7 (SPK-010).

Timeouts (MVP recommendation):
- Cloud Function timeout: `780s` (13 minutes)
- Gemini request deadline: `600s` (10 minutes)
- Reserve `120s` for cleanup/finalize (GCS write + Firestore patch). See `spec/implementation_contract.md`.

Service account must have (minimum):
- Separate identities:
  - **Runtime SA**: the identity the function executes as.
  - **Trigger SA**: the identity Eventarc uses to deliver Firestore events (may be the same as runtime SA).
- Runtime SA (least privilege):
  - Firestore read/write: `roles/datastore.user` (project-level) for `flow_runs/*` and prompt/schema collections.
  - GCS artifacts bucket: bucket-level `roles/storage.objectAdmin`
    - or stricter: `roles/storage.objectCreator` + `roles/storage.objectViewer` (bucket-level).
  - Secret Manager: secret-level `roles/secretmanager.secretAccessor` for the Gemini API key secret.
  - Logging: no IAM role required for stdout/stderr ingestion; add `roles/logging.logWriter` only if calling the Logging API directly.
- Trigger SA (for Firestore/Eventarc):
  - `roles/eventarc.eventReceiver` (project-level).
  - `roles/run.invoker` on the Cloud Run service backing the function.
- MVP (AI Studio): no special IAM for Gemini invocation (uses API key). Service account should have access to Secret Manager to read the API key.
- (future, non-MVP) Vertex AI: Gemini invoke permissions via IAM (e.g., appropriate Vertex AI roles) when switching to ADC/IAM auth.
- Prefer resource-level bindings (bucket/secret) over project-level grants.

### IAM runbook (MVP)

Use placeholders; do not commit real IDs.

1) Runtime SA (Firestore + GCS + Secret Manager):
```bash
gcloud projects add-iam-policy-binding "<PROJECT_ID>" \
  --member="serviceAccount:<RUNTIME_SA_EMAIL>" \
  --role="roles/datastore.user"

gcloud storage buckets add-iam-policy-binding "gs://<ARTIFACTS_BUCKET>" \
  --member="serviceAccount:<RUNTIME_SA_EMAIL>" \
  --role="roles/storage.objectAdmin"

gcloud secrets add-iam-policy-binding "<SECRET_NAME>" \
  --member="serviceAccount:<RUNTIME_SA_EMAIL>" \
  --role="roles/secretmanager.secretAccessor"
```

2) Trigger SA (Eventarc delivery):
```bash
gcloud projects add-iam-policy-binding "<PROJECT_ID>" \
  --member="serviceAccount:<TRIGGER_SA_EMAIL>" \
  --role="roles/eventarc.eventReceiver"

gcloud run services add-iam-policy-binding "<FUNCTION_NAME>" \
  --project "<PROJECT_ID>" \
  --region "<REGION>" \
  --member="serviceAccount:<TRIGGER_SA_EMAIL>" \
  --role="roles/run.invoker"
```

3) If Eventarc delivery returns 403, check the actual caller identity before granting additional roles
   (e.g., Eventarc service agent). Only grant `roles/run.invoker` to the observed caller.

## Dev bootstrap checklist (MVP)

Use placeholders in tracked docs. Do not commit real project IDs, bucket names, or secret names.

### Resources to prepare

- Project + region selected (Firestore DB location must equal function region).
- Firestore database created in the target region.
- Artifacts bucket created (per environment).
- Runtime service account created.
- Trigger service account created (or reuse runtime SA if acceptable).
- Secret Manager secret created for the Gemini API key (`GEMINI_API_KEY`).

### API enablement (first time per project)

```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  run.googleapis.com \
  eventarc.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  logging.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  --project "<PROJECT_ID>"
```

### Firestore DB region check

```bash
gcloud firestore databases list \
  --project "<PROJECT_ID>" \
  --format="table(name,locationId,type)"
```

### IAM bindings

- Apply the **Runtime SA** and **Trigger SA** bindings from the IAM runbook above.
- Prefer bucket/secret-level bindings over project-level grants.

### Deployment inputs (dev)

- Confirm env vars are defined for:
  - `GCP_PROJECT`, `GCP_REGION`, `FIRESTORE_DATABASE`, `FLOW_RUNS_COLLECTION`
  - `LLM_PROMPTS_COLLECTION`, `LLM_MODELS_COLLECTION`
  - `ARTIFACTS_BUCKET`, `GEMINI_TIMEOUT_SECONDS`, `FINALIZE_BUDGET_SECONDS`, `INVOCATION_TIMEOUT_SECONDS`, `LOG_LEVEL`
- Secrets injected via `--set-secrets` (single-key only in MVP).

## Deploy pipeline (dev)

The repository provides a deploy helper script:
- @scripts/deploy_dev.sh

It follows the gcp-functions-gen2-python-deploy playbook and supports:
- first-time vs update deploys,
- Firestore trigger config,
- inline or file-based env vars,
- optional Secret Manager injection,
- optional explicit Cloud Build service account (`BUILD_SA_EMAIL`, email or full resource name).

Before running, export the Deploy request block values as environment variables.
For update deploys, set `CONFIRM_TRIGGER_UNCHANGED=true` unless you intend to change the trigger.

### Lessons learned (dev deploy)

- Missing default compute SA can break deploys. Use `BUILD_SA_EMAIL` to supply a valid build service account.
- `BUILD_SA_EMAIL` must be a full resource name or a valid email; the script normalizes to
  `projects/<PROJECT_ID>/serviceAccounts/<EMAIL>`.
- Existing Cloud Run service with the same name blocks Functions gen2 creation. Delete it or use a new function name.
- Trigger SA must have `roles/eventarc.eventReceiver` and `roles/run.invoker` (on the service) for Firestore triggers.
- Runtime SA must have `roles/secretmanager.secretAccessor` for any Secret Manager–injected env var.
- Python 3.13 runtime + pinned `functions-framework` caused `ImportError: cannot import name 'T' from 're'` in startup;
  rely on the runtime-provided functions-framework instead of pinning in `requirements.txt`.
- Functions Framework can preconfigure the root logger (often at WARNING); ensure INFO logs are emitted by explicitly
  configuring the root handler/formatter (JSON) and log structured dict payloads.

Configuration via environment variables (draft):
- `GCP_PROJECT`
- `GCP_REGION`
- `FIRESTORE_DATABASE` (default `(default)`)
- `FLOW_RUNS_COLLECTION` (default `flow_runs`)
- `LLM_PROMPTS_COLLECTION` (default `llm_prompts`)
- `LLM_MODELS_COLLECTION` (default `llm_models`)
- `ARTIFACTS_BUCKET`
- `ARTIFACTS_PREFIX` (optional)
- `GEMINI_API_KEY` (optional; MVP/AI Studio; prefer injecting from Secret Manager; single-key mode only)
- `GEMINI_LOCATION` (future/Vertex; if applicable)
- `GEMINI_ALLOWED_MODELS` (optional; comma-separated allowlist of model names)
- `GEMINI_TIMEOUT_SECONDS` (MVP, default `600`)
- `FINALIZE_BUDGET_SECONDS` (MVP, default `120`)
- `INVOCATION_TIMEOUT_SECONDS` (MVP, default `780`)
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
- if `GEMINI_ALLOWED_MODELS` is set:
  - it must parse into at least one non-empty model name (comma-separated, trimmed)
  - `steps.<stepId>.inputs.llm.llmProfile.modelName` (or `model`) must be in the allowlist
  - otherwise, fail the step with `LLM_PROFILE_INVALID` (non-retryable)

Secrets:
- MVP uses an API key for AI Studio. Store it in Secret Manager and inject into the function as an environment variable (do not commit it, do not log it).

### Gemini API key management (MVP / AI Studio)

Goal: keep the API key out of code/commits and guarantee the key is never emitted in logs or persisted artifacts.

Single-key only (MVP):
- `GEMINI_API_KEY` is the only supported secret input.
- Inject it via Secret Manager → env var; do not commit or log it.

#### Deployment: Secret Manager → env var injection (Cloud Functions gen2)

Inject secrets via deployment config, not via committed files.

Example (illustrative; exact flags may vary by environment):
- set secret env var: `GEMINI_API_KEY` from Secret Manager (`:latest` or pinned version)

Notes:
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

## Smoke checks (dev runbook)

Use placeholders only. This runbook is safe for `dev` and can be run after deploy/update.

### 1) Trigger an update

- Create or update a `flow_runs/{runId}` document so the Firestore **update** trigger fires.
- For a full pipeline check, use the test vectors under @docs/test_vectors/inputs and set one
  `LLM_REPORT` step to `READY` with dependencies `SUCCEEDED`.
- For the stub-only deploy, any update to the document is sufficient (the stub logs the event).

### 2) Verify Cloud Logging (Cloud Run revision logs)

Filter by service + recent time:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision"
   resource.labels.service_name="<FUNCTION_NAME>"
   timestamp>="<RFC3339_START>"' \
  --project "<PROJECT_ID>" \
  --limit 50
```

For the **stub**, look for `stub invocation` in `textPayload`.
For the real worker, validate the expected event chain using `jsonPayload.event`:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision"
   resource.labels.service_name="<FUNCTION_NAME>"
   jsonPayload.event="cloud_event_received"' \
  --project "<PROJECT_ID>" \
  --limit 50
```

Optionally narrow by run/step:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision"
   resource.labels.service_name="<FUNCTION_NAME>"
   jsonPayload.runId="<RUN_ID>"' \
  --project "<PROJECT_ID>" \
  --limit 50
```

### 3) Verify Firestore step status (real worker only)

- Ensure the `LLM_REPORT` step transitioned to `SUCCEEDED`.
- Confirm `steps.<stepId>.outputs.gcs_uri` is populated.

### 4) Verify GCS artifact (real worker only)

```bash
gcloud storage ls "gs://<ARTIFACTS_BUCKET>/<runId>/<timeframe>/<stepId>.json"
```
