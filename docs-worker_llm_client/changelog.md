# Changelog for docs-worker_llm_client

## Format

For every meaningful Git commit that changes this documentation pack, add a new entry here in the same commit:
- What changed (concrete, file-level if useful)
- Why it changed (decision / intent)
- Checklist delta (if any)
- Open questions delta (if any)

## Entries

### Unreleased

- Closed prompt-related blockers: defined minimal MVP Firestore prompt document contract `llm_prompts/{promptId}` (schema + example), specified context injection policy (JSON as text, images as inline bytes, 64KB per-JSON limit, 256KB per-image limit), and decided `scope` is injected via **UserInput** (`contracts/llm_prompt.*`, `contracts/examples/llm_prompt.example.json`, `spec/prompt_storage_and_context.md`, `spec/system_integration.md`, `spec/implementation_contract.md`, `spec/error_and_retry_model.md`, `questions/open_questions.md`).
- Added MVP implementation guidance to reuse proven code via copy-paste from `worker_chart_export` and `worker_ohlcv_export` (logging, CloudEvent parsing, Firestore precondition claim/finalize), keeping this spec pack as the source of truth (`spec/implementation_contract.md`, `spec/handoff_checklist.md`).
- Closed CloudEvent subject parsing open question: documented observed Eventarc gen2 subject pattern (`documents/flow_runs/<runId>`) and strict runId extraction/validation rules (`spec/system_integration.md`, `spec/implementation_contract.md`, `questions/open_questions.md`).
- Closed logging taxonomy open question: standardized structured log envelope fields and added a concrete event catalog + typical ordering for `worker_llm_client` (`spec/observability.md`, `questions/open_questions.md`).
- Closed additional orchestration/error-handling open questions: dependsOn satisfaction rules, timing field placement, missing-dependency failure policy, deterministic GCS reuse on split-brain finalize, optimistic preconditions (no transactions), no flowRunSteps truncation on MVP, no indexing storage on MVP, orchestrator vs worker responsibility, safety block mapping, AI Studio endpoint for MVP, and reaper/out-of-scope zombie recovery (`spec/*.md`, `contracts/flow_run.md`, `questions/open_questions.md`).
- Closed timeout policy open question: set Gemini request deadline to `600s` (10m), Cloud Function timeout to `780s` (13m), and reserved `120s` finalize budget (`spec/implementation_contract.md`, `spec/deploy_and_envs.md`, `spec/error_and_retry_model.md`, `questions/open_questions.md`).
- Decided Gemini request parameters are provided only via `steps.*.inputs.llm.llmProfile` (no overrides from prompt/model defaults), updated canonical contracts/examples/test vectors accordingly, and closed open question #1 (`contracts/*.json`, `contracts/examples/*.json`, `test_vectors/*`, `spec/*.md`, `questions/open_questions.md`).
- Added first-pass spec pack for `worker_llm_client` (Cloud Functions gen2 Firestore-triggered LLM step executor) and filled core spec sections (`spec/*.md`).
- Promoted `flow_run` schema and example into canonical contracts (`contracts/flow_run.schema.json`, `contracts/examples/flow_run.example.json`) and added a human-readable contract note (`contracts/flow_run.md`).
- Promoted canonical JSON Schema for the LLM report JSON file (`contracts/llm_report_file.schema.json`) with an example.
- Added initial test vectors for a `READY` `LLM_REPORT` step and an error scenario (missing prompt) under `test_vectors/`.
- Updated `questions/open_questions.md` with blockers around Gemini request parameters, persisted metadata, artifact naming, and logging event taxonomy.
- Updated checklist completion for covered items (`checklists/component_docs_checklist.ru.md`).
- Expanded the error/retry model with a stable error-code proposal, partial-failure handling patterns, Firestore contention notes, and reference retry parameters (`spec/error_and_retry_model.md`).
- Updated logging contract to include `service`/`env`, CloudEvent correlation (`eventId`), and a stable snake_case event taxonomy aligned with Cloud Logging expectations (`spec/observability.md`).
- Added `cloud_event_parsed` requirement to include compact `flowRunSteps` summaries (id/stepType/status/dependsOn) without leaking step inputs (`spec/observability.md`).
- Added Cloud Functions gen2 performance/scaling notes (Cloud Run-like concurrency and instance bounds; start with `--concurrency=1`) (`spec/architecture_overview.md`).
- Added Python implementation conventions (PEP 8, typing, docstrings, error handling, logging) and env-var style guidance (`spec/implementation_contract.md`, `spec/deploy_and_envs.md`).
- Documented orchestration assumptions (`advance_flow` sets `PENDING→READY`) and future optional `reports/*` indexing; refined open questions to reflect prototype constraints (metadata-in-logs, no attempt history, signed URLs) (`spec/system_integration.md`, `spec/implementation_contract.md`, `questions/open_questions.md`).
- Recorded decisions: persist extended LLM execution metadata in `flow_run`, deterministic GCS naming without attempts/timestamps, and store only `gcs_uri` (no `signed_url`) (`spec/system_integration.md`, `spec/implementation_contract.md`, `questions/open_questions.md`).
- Set canonical GCS URI format to `gs://...` and updated the LLM report file schema accordingly; refreshed `questions/open_questions.md` with the remaining unresolved decisions needed for implementation. (`contracts/llm_report_file.schema.json`, `questions/open_questions.md`).
- Added “semantic gap” open questions around context injection, orchestrator/worker responsibility boundaries, Gemini safety blocking, prompt scope merging, SDK choice, timeouts, and zombie-step recovery (`questions/open_questions.md`).
- Triaged inbox notes on artifact naming + Gemini structured output: standardized GCS artifact paths under `/<runId>/<timeframe>/<stepId>.json`, introduced storage-safe `stepId` canon, switched `LLM_REPORT` inputs to stepId references (`ohlcvStepId`, `chartsManifestStepId`), expanded LLM report file schema with finish metadata (finishReason/modelVersion/usageMetadata), refreshed examples/test vectors, and deleted processed inbox artifacts (`spec/*.md`, `contracts/*.json`, `contracts/examples/*.json`, `test_vectors/*`, `inbox/*`).
- Adjusted `llm_report_file` shape so model structured output lives under `output` (with `output.summary` + `output.details`) while `metadata` remains worker-provided (`contracts/llm_report_file.schema.json`, `contracts/examples/llm_report_file.example.json`).
