# Architecture overview

## Role in the overall system

`worker_llm_client` executes **LLM steps** inside Trading Decision Assistant workflows.

Runtime:
- **Google Cloud Functions (gen2)** (Cloud Run Functions)
- Trigger: **Firestore document update events** for `flow_runs/{runId}`

The worker is responsible for:
- selecting a `READY` step with `stepType=LLM_REPORT`
- claiming it atomically (`READY → RUNNING`) using Firestore optimistic preconditions
- calling Google Gemini with prompt + context
- writing the produced artifact to Cloud Storage
- persisting execution metadata back into `flow_runs/{runId}` and completing the step (`RUNNING → SUCCEEDED/FAILED`)

Out of scope (for this component):
- producing OHLCV exports and charts (upstream steps)
- orchestrating the whole workflow (which step becomes `READY`)
- user-facing delivery of reports

## Dependencies (inbound/outbound)

Inbound:
- Firestore update CloudEvents for `flow_runs/{runId}`

Outbound:
- Firestore read/write:
  - `flow_runs/{runId}` (read + step status patches)
  - prompt/instruction docs (exact collections TBD; see `questions/open_questions.md`)
- Cloud Storage:
  - read upstream artifacts referenced by the step (e.g., OHLCV JSON, charts manifest)
  - write LLM output artifact (JSON preferred; Markdown optional)
- Google Gemini API (MVP: AI Studio endpoint) for text generation / structured output
- Cloud Logging for structured logs

## High-level flows

1. Firestore update event arrives for `flow_runs/{runId}`
2. Worker parses `runId` from CloudEvent `subject`
3. Worker fetches `flow_runs/{runId}`
4. Worker selects a `READY` step with `stepType=LLM_REPORT` whose `dependsOn` steps are all `SUCCEEDED`
5. Worker atomically claims the step using update precondition (`update_time`)
6. Worker loads prompt/instructions by ID from Firestore (and resolves model config)
7. Worker loads any context artifacts (GCS URIs in the step inputs)
8. Worker executes Gemini request (prefer structured output → JSON)
9. Worker writes output artifact to GCS
10. Worker patches Firestore step outputs + metadata and marks step `SUCCEEDED` (or `FAILED`)

## Performance and scaling (Cloud Functions gen2)

Cloud Functions gen2 runs on Cloud Run infrastructure, so scaling knobs are Cloud Run–like:
- `--concurrency`: max concurrent requests per instance (container).
- `--max-instances` / `--min-instances`: instance scaling bounds.

Guidance for this worker:
- no multithreading inside the process
- prefer horizontal scaling (more instances) over internal threads
- start with `--concurrency=1` for safety (avoids overlapping Firestore updates and shared-client/thread-safety issues)
- increase concurrency only after proving the implementation is concurrency-safe and quotas/costs are acceptable
