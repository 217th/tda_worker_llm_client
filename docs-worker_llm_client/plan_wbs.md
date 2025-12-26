# Plan / WBS for worker_llm_client

Describe epic-level increments (3–10) with product value and acceptance criteria.

Recommended format: a short table (or headings), per epic.

| Epic | Phase (MVP/post‑MVP/hardening) | What changes | Why it matters | How to accept |
|------|--------------------------------|-------------|----------------|---------------|
| Epic 1: Firestore-triggered step executor | MVP | Cloud Function (gen2) triggered by `flow_runs/{runId}` updates; selects `READY` `LLM_REPORT`, checks `dependsOn`, claims via precondition, executes, finalizes step | End-to-end ability to produce LLM report artifacts as part of flows | Update a run doc with a `READY` step and observe `READY→RUNNING→SUCCEEDED` + `outputs.gcs_uri` |
| Epic 2: Prompt config + LLM profiles | MVP | Define Firestore collection(s) for prompts and validate `inputs.llm.llmProfile` allowlist; (optional) add `llm_profiles/{profileId}` for reuse/versioning | Decouple prompts and request params from code and enable safe iteration | Changing `promptId`/`llmProfile` in a step switches behavior without deploy |
| Epic 3: Structured output (JSON) | MVP | Use Gemini structured output / JSON schema; validate outputs; store JSON artifact | Machine-readable reports for downstream automation | Artifact JSON validates against expected schema; failures are handled predictably |
| Epic 4: Artifact naming + retention | post‑MVP | Finalize deterministic GCS naming; add expiry/retention strategy; optional cleanup job | Idempotency and cost control | Replays do not duplicate artifacts; old artifacts are retained/cleaned per policy |
| Epic 5: Observability baseline | MVP | Implement structured logging contract and baseline event taxonomy; define metrics and filters | Debuggability and operability from day 1 | Logs contain required fields and can be filtered by `runId/stepId` |
| Epic 6: Reliability hardening | hardening | Robust retries/backoff, rate limiting, partial-failure handling, optional DLQ/retry queue | Stable operation under load and transient failures | Chaos test: inject transient errors, confirm retries and correct final states |
| Epic 7: QA harness + offline CI | post‑MVP | Add emulator-based tests, fixtures, golden test vectors for key scenarios | Fast safe iteration | CI can run without real GCP; key scenarios covered |
| Epic 8: Security and policy | hardening | Secrets/PII policy, model allowlist, safety settings policy, redaction | Prevent data leaks and policy violations | Security review passes; logs contain no sensitive data |

Notes:
- If you need non-local environments (dev/test/prod) beyond local runs, consider a dedicated epic for environment setup + deploy/run process (docker/k8s/serverless, CI/CD, runbooks).
