# Open questions for worker_llm_client

Keep this file current. Close questions explicitly (with decision + date/commit reference) or reword them precisely.

## Questions

| ID | Priority | Blocks planning? | Question | Current best guess | Owner | Target date |
|---:|:--------:|:---------------:|----------|--------------------|-------|-------------|
| 1 | High | Yes | Какие параметры должны поддерживаться в запросе к Gemini (temperature/topP/topK/maxOutputTokens/stopSequences/responseSchema/…) и какие из них можно переопределять на уровне шага vs на уровне prompt/model? | Support the common GenerationConfig set + structured output knobs; exact allowlist TBD | TBD | TBD |
| 5 | High | Yes | Какой “набор событий” и обязательные поля структурированных логов должен использоваться (есть наработки из прошлых проектов)? | Proposed: stable snake_case events + required `service/env/runId/stepId/eventId` + `flowKey/timeframe/symbol` when known; needs alignment | TBD | TBD |
| 6 | Medium | No | Точный формат CloudEvent `subject` для Firestore update trigger (что именно приходит в gen2) и требования к парсеру `runId`. | Parse last segment after `flow_runs/`; confirm real subject samples | TBD | TBD |
| 7 | High | Yes | Где именно и в каком формате хранить инструкции: структура документа `llm_prompts/{promptId}` (поля, шаблонизация, версия, input/output schema). | Store system + user templates and optional schemas; finalize schema later | TBD | TBD |
| 8 | Medium | No | Политика по `dependsOn`: считать ли `SKIPPED` как удовлетворённую зависимость или только `SUCCEEDED`? | Only `SUCCEEDED` for now (per current requirement) | TBD | TBD |
| 11 | Medium | No | Где хранить времена выполнения шага: добавляем `steps.*.startedAt` в схему `flow_run` или храним только внутри `steps.*.outputs.execution.timing`? | Prefer `outputs.execution.timing.startedAt/finishedAt/durationMs` (keeps base schema stable) | TBD | TBD |
| 12 | Medium | No | Что делать, если `dependsOn` ссылается на несуществующий `stepId` (data corruption / wrong flow definition): no-op vs `FAILED`? | Probably `FAILED` as configuration error (but confirm) | TBD | TBD |
| 13 | High | Yes | Политика при `INVALID_STRUCTURED_OUTPUT`: ретраить (repair prompt) vs сразу `FAILED`? Сколько попыток? | Likely 1 repair attempt max; otherwise `FAILED` | TBD | TBD |
| 14 | Medium | No | Как поступать, если детерминированный объект в GCS уже существует, но в Firestore нет финализации (split-brain): можно ли “переиспользовать” объект и просто финализировать? | Yes: treat as success and finalize without re-calling LLM | TBD | TBD |
| 15 | Medium | No | Firestore claim/finalize: стандартизируем ли по всем воркерам подход “optimistic precondition (update_time)” вместо транзакций? В prototype упоминается транзакция, а для этого воркера мы избегаем транзакций. | Prefer preconditions + short retries to avoid contention | TBD | TBD |
| 16 | Low | No | Нужен ли лимит/трейдофф для `cloud_event_parsed.flowRunSteps` (триггер может включать много шагов): сколько максимум и как сигнализировать `truncated=true`? | Add `maxStepsLogged` and `truncated` fields | TBD | TBD |
| 17 | Low | No | Нужно ли отдельное “indexing” хранилище (`reports/*`) на MVP, или достаточно `flow_run` + GCS? | Likely post-MVP | TBD | TBD |
| 18 | High | Yes | **Механизм инъекции контекста в Prompt:** Как именно worker передает содержимое артефактов (резолвим по `ohlcvStepId`/`chartsManifestStepId`) в Gemini? Скачивает JSON и вставляет как текст (Token count risk!) или передает как file-part/URI (если SDK поддерживает)? | Скорее всего, скачиваем JSON и вставляем в текст промпта (text injection), т.к. “самоскачивание” по ссылкам моделью не гарантировано. | TBD | TBD |
| 19 | High | Yes | **Responsibility Overlap (Orchestrator vs Worker):** Если worker ставит шагу статус `FAILED` (фатальная ошибка), должен ли *worker* переводить весь `flow_run` в `FAILED`, или это задача триггера `advance_flow`? | Worker обновляет только шаг. Оркестратор (`advance_flow`) реагирует на update и закрывает flow, если политика требует остановки. | TBD | TBD |
| 20 | Medium | No | **Обработка Safety Ratings:** Как мапить блокировку генерации моделью (Safety Filter triggered)? Это техническая ошибка (retryable) или логическая (FAILED)? Артефакт `llm_report_file` требует обязательные поля `summary/details`, которых не будет при блокировке. | Считать `FAILED` с кодом `LLM_SAFETY_BLOCK`. Сохранять "пустой" репорт с метаданными о блоке, либо писать ошибку в step.error. | TBD | TBD |
| 21 | Medium | No | **Интеграция `scope` в Prompt:** В `flow_run` есть поле `scope` (глобальные параметры, например `symbol`). Доступно ли оно автоматически внутри шаблона промпта, или его нужно явно пробрасывать через `inputs` шага? | `scope` должен мерджиться в контекст шаблонизатора промпта по умолчанию. | TBD | TBD |
| 22 | High | Yes | **Выбор SDK/API Endpoint:** Используем ли мы `google-generativeai` (AI Studio) или `google-cloud-aiplatform` (Vertex AI)? Это влияет на Auth (API Key vs ADC/IAM) и доступность регионов (`GEMINI_LOCATION`). | Vertex AI (`google-cloud-aiplatform`) с ADC (Application Default Credentials) для production-grade безопасности и IAM. | TBD | TBD |
| 23 | Medium | No | **Timeout Policy:** Какой таймаут ставить на вызов Gemini внутри Cloud Function? Учитывая, что сама функция имеет таймаут (макс 60m в gen2), сколько оставлять на "cleanup/finalize" при зависании модели? | Gemini timeout = Function timeout - 30s (на финализацию и запись ошибки). | TBD | TBD |
| 24 | Medium | No | **Zombie Steps Recovery:** В `spec/error_and_retry_model.md` сказано "define a recovery policy outside this worker". Означает ли это, что worker *вообще* не должен обрабатывать кейс "завис в RUNNING > N минут"? | Да, worker не занимается "сборкой мусора". Это задача отдельного `reaper` джоба или логики оркестратора. | TBD | TBD |

## Decisions (closed)

| ID | Date | Decision |
|---:|:----:|----------|
| 2 | 2025-12-24 | Храним **расширенные метаданные** LLM выполнения в `flow_run` (tokens/finishReason/safety/requestId/latency/…), не только в логах. |
| 3 | 2025-12-24 | Канонический артефакт отчёта в GCS — **один JSON файл** по `contracts/llm_report_file.schema.json` (внутри есть `output.summary.markdown` и `output.details`). |
| 4 | 2025-12-26 | GCS naming — **детерминированный путь** `/<runId>/<timeframe>/<stepId>.json`, без `attempt` и без не-детерминированных timestamp в имени; `stepId` storage-safe (без `/ . :` и т.п.). |
| 9 | 2025-12-24 | В `flow_run` сохраняем только `gcs_uri` (без `signed_url`). |
| 10 | 2025-12-24 | Канонический формат GCS URI — `gs://...` (в контрактах используем `^gs://`). |
