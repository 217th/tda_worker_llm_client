# Open questions for worker_llm_client

Keep this file current. Close questions explicitly (with decision + date/commit reference) or reword them precisely.

## Questions

| ID | Priority | Blocks planning? | Question | Current best guess | Owner | Target date |
|---:|:--------:|:---------------:|----------|--------------------|-------|-------------|
| 5 | High | Yes | Какой “набор событий” и обязательные поля структурированных логов должен использоваться (есть наработки из прошлых проектов)? | Proposed: stable snake_case events + required `service/env/runId/stepId/eventId` + `flowKey/timeframe/symbol` when known; needs alignment | TBD | TBD |
| 6 | Medium | No | Точный формат CloudEvent `subject` для Firestore update trigger (что именно приходит в gen2) и требования к парсеру `runId`. | Parse last segment after `flow_runs/`; confirm real subject samples | TBD | TBD |
| 13 | High | Yes | Политика при `INVALID_STRUCTURED_OUTPUT`: ретраить (repair prompt) vs сразу `FAILED`? Сколько попыток? | Likely 1 repair attempt max; otherwise `FAILED` | TBD | TBD |
| 23 | Medium | No | **Timeout Policy:** Какой таймаут ставить на вызов Gemini внутри Cloud Function? Учитывая, что сама функция имеет таймаут (макс 60m в gen2), сколько оставлять на "cleanup/finalize" при зависании модели? | Gemini timeout = Function timeout - 30s (на финализацию и запись ошибки). | TBD | TBD |

## Decisions (closed)

| ID | Date | Decision |
|---:|:----:|----------|
| 1 | 2025-12-26 | Gemini request parameters are provided only via `steps.*.inputs.llm.llmProfile` (authoritative; no overrides from prompt/model defaults). Allowlist: `model/modelName`, `temperature`, `topP`, `topK`, `maxOutputTokens`, `stopSequences`, `candidateCount`, `responseMimeType`, `responseSchema/jsonSchema`, `thinkingConfig(includeThoughts, thinkingLevel)`. |
| 2 | 2025-12-24 | Храним **расширенные метаданные** LLM выполнения в `flow_run` (tokens/finishReason/safety/requestId/latency/…), не только в логах. |
| 3 | 2025-12-24 | Канонический артефакт отчёта в GCS — **один JSON файл** по `contracts/llm_report_file.schema.json` (внутри есть `output.summary.markdown` и `output.details`). |
| 4 | 2025-12-26 | GCS naming — **детерминированный путь** `/<runId>/<timeframe>/<stepId>.json`, без `attempt` и без не-детерминированных timestamp в имени; `stepId` storage-safe (без `/ . :` и т.п.). |
| 9 | 2025-12-24 | В `flow_run` сохраняем только `gcs_uri` (без `signed_url`). |
| 10 | 2025-12-24 | Канонический формат GCS URI — `gs://...` (в контрактах используем `^gs://`). |
| 7 | 2025-12-26 | Prompt instructions live in Firestore collection `llm_prompts/{promptId}`; canonical schema is `contracts/llm_prompt.schema.json` (with notes in `contracts/llm_prompt.md` + example `contracts/examples/llm_prompt.example.json`). MVP required fields: `schemaVersion=1`, `systemInstruction` (string), `userPrompt` (string). Versioning is encoded in `promptId` by convention (`*_v1`, `*_v2`, ...). |
| 18 | 2025-12-26 | Context injection policy: worker downloads required artifacts from GCS itself (do not rely on model-side HTTP downloads). JSON artifacts (OHLCV, charts manifest, previous reports) are injected as text parts (fenced JSON blocks) with a hard per-artifact size limit of **64KB**; if exceeded, fail with `INVALID_STEP_INPUTS`. Chart images are passed as inline bytes (file/data parts) when supported, with a hard per-image limit of **256KB**; if exceeded, fail with `INVALID_STEP_INPUTS`. Additionally, worker appends a generated **UserInput** section listing each chart with a short description (prefer description copied into charts manifest from chart_template). |
| 21 | 2025-12-26 | `flow_run.scope` is injected into the prompt via the generated **UserInput** section (e.g., `Symbol: <scope.symbol>`). It does not need to be re-passed through step inputs unless an explicit override is required. |
| 8 | 2025-12-27 | `dependsOn` is satisfied only by `SUCCEEDED`. `SKIPPED` does **not** satisfy dependencies. |
| 11 | 2025-12-27 | Step timing is stored under `steps.<stepId>.outputs.execution.timing` (`startedAt/finishedAt/durationMs`). Do not add `steps.<stepId>.startedAt` to the `flow_run` schema. |
| 12 | 2025-12-27 | If `dependsOn` references a non-existent `stepId`, treat it as a configuration error and mark the step `FAILED` (non-retryable). |
| 14 | 2025-12-27 | Split-brain handling: if the deterministic GCS object already exists but Firestore was not finalized, the worker may reuse the object and finalize the step without re-calling the LLM. |
| 15 | 2025-12-27 | Standardize on Firestore optimistic preconditions (`update_time`) for claim/finalize (no Firestore transactions) across workers. |
| 16 | 2025-12-27 | MVP: no truncation/limits for `cloud_event_parsed.flowRunSteps` are required. Log all step summaries (still without inputs). |
| 17 | 2025-12-27 | MVP: `flow_run` + GCS is sufficient; no separate indexing storage (`reports/*`) on MVP. |
| 19 | 2025-12-27 | Worker updates only the step (`READY→RUNNING→SUCCEEDED/FAILED`). Orchestrator (`advance_flow`) reacts to step updates and decides `flow_run.status` terminal transitions. |
| 20 | 2025-12-27 | Safety blocks are treated as `FAILED` with error code `LLM_SAFETY_BLOCK` (non-retryable). Artifact write is optional; if written, it must not violate the canonical `llm_report_file` schema. |
| 22 | 2025-12-27 | MVP uses **AI Studio** endpoint (API key auth). Production may move to Vertex AI later (ADC/IAM). |
| 24 | 2025-12-27 | Zombie step recovery is out of scope for the worker. A separate reaper job or orchestrator policy handles stuck `RUNNING` steps. |
