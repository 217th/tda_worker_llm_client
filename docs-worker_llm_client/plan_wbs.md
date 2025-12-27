# Plan / WBS for worker_llm_client

Этот план — актуализированная WBS, синхронизированная с `static_model.md`.

Требование: **все классы из `static_model.md` распределены по эпикам** (см. таблицу “Class allocation” в конце).

## Epic overview

| Epic | Phase | Value | How to accept |
| --- | --- | --- | --- |
| Epic 0 — Cloud environment + deploy pipeline | MVP | Возможность повторяемо деплоить/обновлять сервис в Cloud (Cloud Functions gen2 / Cloud Run) и проверять результаты по Cloud Logging | В `dev` окружении есть пайплайн деплоя + smoke-check сценарии + чеклист верификации через логи/артефакты |
| Epic 1 — Runtime config + secrets | MVP | Безопасная конфигурация сервиса и аутентификации Gemini (Secret Manager → env vars, ротация) | Конфиг валидируется на старте; ключи не логируются/не персистятся; поддержана ротация через `GEMINI_API_KEYS_JSON` + `GEMINI_API_KEY_ID` |
| Epic 2 — Observability baseline | MVP | Структурированные логи с устойчивой таксономией событий и полями корреляции | Любой run/step можно найти по `runId/stepId/eventId`; отсутствуют prompt/raw output/секреты |
| Epic 3 — Workflow domain + step selection | MVP | Доменная модель `flow_runs/{runId}` и детерминированный выбор исполняемого `LLM_REPORT` шага | На входных векторах (READY/no-op/blocked) корректно выбирается/не выбирается шаг; ошибки мапятся на стабильные `error.code` |
| Epic 4 — Firestore FlowRun I/O + optimistic concurrency | MVP | Надёжные `READY→RUNNING` claim и `RUNNING→SUCCEEDED/FAILED` finalize с `update_time` preconditions (без транзакций) | При гонке claim/finalize второй воркер не портит состояние и не создаёт side effects |
| Epic 5 — Prompt + schema registry integration | MVP | Получение prompt’ов и JSON Schema из Firestore (как источников правды) | Изменение `promptId`/`schemaId` в step меняет поведение без деплоя; отсутствующие/битые документы дают предсказуемые ошибки |
| Epic 6 — Artifacts (GCS) + canonical report file | MVP | Детерминированные URIs, create-only запись артефактов, канонический `LLMReportFile` | Повторы не создают дублей; split-brain finalize реюзает объект; артефакт соответствует `contracts/llm_report_file.schema.json` |
| Epic 7 — LLM execution + structured output validation/repair | MVP | Сборка UserInput, вызов Gemini, детерминированная валидация structured output (+ 1 repair попытка по политике) | Успех → валидный JSON; неуспех → `INVALID_STRUCTURED_OUTPUT`/`LLM_PROFILE_INVALID` по правилам, без утечек payload |
| Epic 8 — Invocation orchestration + time budgets | MVP | Склейка всего пайплайна в CloudEvent handler с охраной time budget | Не стартуем внешние вызовы при недостатке времени; корректно финализируем шаги и логируем исход |

## Epic details

### Epic 0 — Cloud environment + deploy pipeline (MVP)

- Classes: — (инфраструктурный эпик; классы из `static_model.md` не добавляет)
- Spikes (from `questions/arch_spikes.md`): `SPK-017`, `SPK-018`
- What changes:
  - Создание минимального `dev` окружения в GCP для `worker_llm_client`: проект/регион, Firestore, bucket для артефактов, Secret Manager, service account + IAM.
  - Автоматизированный деплой в Cloud (Cloud Functions gen2 / Cloud Run) + быстрый апдейт ревизий.
  - Runbook/скрипты проверки результатов через Cloud Logging (по `jsonPayload.event`) и через наличие артефактов в GCS.
- Why it matters: все “cloud demo” для следующих эпиков должны быть воспроизводимыми (без ручной магии), иначе приёмка будет нестабильной.
- Definition of done — cloud (dev):
  - Деплой/обновление сервиса выполняется одной командой/пайплайном (CI или `make deploy-dev`), без ручного кликанья в консоли.
  - Есть smoke-сценарий, который:
    - создаёт/обновляет `flow_runs/{runId}` так, чтобы сработал триггер,
    - проверяет через Cloud Logging наличие ожидаемой последовательности событий (`cloud_event_received` → … → `cloud_event_finished`),
    - (когда реализовано) проверяет наличие артефакта в GCS и заполнение `steps.<stepId>.outputs.gcs_uri`.
  - Есть documented log queries/filters для быстрой верификации по `runId/stepId/eventId` и `env`.
- Where to test/demo:
  - Cloud: `dev` (обязательное; этот эпик и есть построение Cloud среды).

### Epic 1 — Runtime config + secrets (MVP)

- Classes: `WorkerConfig`, `GeminiApiKey`, `GeminiAuthConfig`
- Spikes (from `questions/arch_spikes.md`): `SPK-001` (done), `SPK-007`, `SPK-020`
- What changes:
  - Валидация env-конфига и секретов на старте процесса.
  - Поддержка single-key (`GEMINI_API_KEY`) и rotation-friendly multi-key (`GEMINI_API_KEYS_JSON` + `GEMINI_API_KEY_ID`).
- Why it matters: безопасная эксплуатация и управляемая ротация без утечек.
- Definition of done — local:
  - Unit tests на `WorkerConfig.from_env()` покрывают:
    - single-key (`GEMINI_API_KEY`) happy-path,
    - multi-key (`GEMINI_API_KEYS_JSON` + `GEMINI_API_KEY_ID`) happy-path,
    - ошибки валидации (битый JSON/пустые поля/неизвестный keyId) без утечки значения секрета.
  - Негативный тест: в тексте исключений/логов нет `apiKey` и нет его хеша.
- Definition of done — cloud (dev; requires Epic 0):
  - Секрет инжектится через Secret Manager → env var, и сервис стартует без ручной подмены.
  - В Cloud Logging подтверждается, что логируется только `llm.auth.mode` и опционально `llm.auth.keyId`.
- Where to test/demo:
  - Local: да (юнит-тесты/линтинг).
  - Cloud: да, `dev` (через деплой из Epic 0).

### Epic 2 — Observability baseline (MVP)

- Classes: `EventLogger`, `CloudLoggingEventLogger`
- Spikes (from `questions/arch_spikes.md`): `SPK-013`
- What changes:
  - Единая обёртка логирования с обязательными полями и устойчивыми event names.
- Why it matters: дебаг/алерты/операционка без “снежинок” в логах.
- Definition of done — local:
  - Unit tests подтверждают, что `EventLogger`:
    - требует обязательные поля (service/env/component/event/time/…),
    - не принимает “опасные” поля (например, дамп `os.environ`) и не логирует секреты по ошибке.
  - Golden-тесты (или snapshot) на ключевые события: `cloud_event_received`, `cloud_event_parsed`, `claim_attempt`, `llm_request_started`, `gcs_write_finished`, `step_completed/step_failed`.
- Definition of done — cloud (dev; requires Epic 0):
  - В Cloud Logging можно фильтровать и собирать цепочку одного запуска по `runId/stepId/eventId`.
  - Для одного smoke-run видна ожидаемая последовательность событий (как в `spec/observability.md`), без prompt/raw output/секретов.
- Where to test/demo:
  - Local: да (юнит-тесты + snapshot).
  - Cloud: да, `dev` (через деплой из Epic 0).

### Epic 3 — Workflow domain + step selection (MVP)

- Classes: `FlowRun`, `FlowStep`, `LLMReportStep`, `LLMReportInputs`, `ReadyStepSelector`, `StepError`, `ErrorCode`
- Spikes (from `questions/arch_spikes.md`): `SPK-011`, `SPK-019`
- What changes:
  - Доменная модель шага и проверка инвариантов, необходимых для `worker_llm_client`.
  - Детерминированный выбор одного исполняемого READY шага.
- Why it matters: предсказуемое поведение под дубликатами/переупорядочиванием событий.
- Definition of done — local:
  - Unit tests на `ReadyStepSelector`:
    - no-op, если `flow_run.status != RUNNING`,
    - no-op, если нет `READY` `LLM_REPORT`,
    - детерминированный выбор при нескольких `READY` (лексикографически по `stepId`),
    - guard: зависимости удовлетворяются только `SUCCEEDED`.
  - Unit tests на `LLMReportInputs`:
    - корректная резолюция `ohlcvStepId/chartsManifestStepId/previousReportStepIds`,
    - ошибки `INVALID_STEP_INPUTS` при отсутствующих шагах/`outputs.gcs_uri`.
- Where to test/demo:
  - Local: да (чистая доменная логика; без Cloud).
  - Cloud: опционально (демо косвенно через Epic 8).

### Epic 4 — Firestore FlowRun I/O + optimistic concurrency (MVP)

- Classes: `FlowRunRepository`, `FirestoreFlowRunRepository`, `ClaimResult`, `FinalizeResult`
- Spikes (from `questions/arch_spikes.md`): `SPK-003`, `SPK-004`, `SPK-005`
- What changes:
  - Реализация claim/finalize через: read snapshot → gate по статусу → update с `last_update_time` precondition → короткие retries на `FailedPrecondition/Conflict/Aborted`.
- Why it matters: “at most one claimant” и корректная работа при гонках без транзакций.
- Definition of done — local:
  - Unit tests на репозиторий через fake snapshot/update_time:
    - claim: `READY → RUNNING` успех,
    - claim: гонка → `precondition_failed` и no-op,
    - finalize: `already_final` и no-op,
    - finalize: `not_running` и no-op.
  - Отдельный тест/проверка: `stepId` с `.` не допускается (иначе dotted-path update некорректен).
- Definition of done — cloud (dev; requires Epic 0):
  - Запуск двух конкурентных инвокаций (естественно через duplicate events или ручной параллельный update) не приводит к двум LLM вызовам и двойным артефактам.
  - В логах видно `claim_attempt` с `claimed=true` ровно один раз на step.
- Where to test/demo:
  - Local: да (юнит-тесты с фейками).
  - Cloud: да, `dev` (через деплой из Epic 0; реальная Firestore contention).

### Epic 5 — Prompt + schema registry integration (MVP)

- Classes: `PromptRepository`, `FirestorePromptRepository`, `SchemaRepository`, `FirestoreSchemaRepository`, `LLMPrompt`, `LLMSchema`
- Spikes (from `questions/arch_spikes.md`): `SPK-006`, `SPK-016`
- What changes:
  - Чтение `llm_prompts/{promptId}` и `llm_schemas/{schemaId}` из Firestore.
  - Предпроверки: prompt/schema must exist; schema must satisfy minimal invariants policy.
- Why it matters: быстрое развитие prompt/schema без деплоя и без неопределённости “какая версия”.
- Definition of done — local:
  - Unit tests: маппинг ошибок репозиториев:
    - missing prompt → `PROMPT_NOT_FOUND`,
    - missing schema / schema не удовлетворяет минимальным инвариантам → `LLM_PROFILE_INVALID`,
    - transient Firestore → retryable `FIRESTORE_UNAVAILABLE` (как доменная ошибка/исключение).
- Definition of done — cloud (dev; requires Epic 0):
  - В `dev` Firestore заведены тестовые документы `llm_prompts/{promptId}` и `llm_schemas/{schemaId}`.
  - Smoke-run проходит до LLM вызова, и в логах есть `prompt_fetch_*` и `structured_output_schema_invalid` (для негативного случая) без вызова Gemini.
- Where to test/demo:
  - Local: да (юнит-тесты с фейками/фикстурами).
  - Cloud: да, `dev` (реальная Firestore интеграция).

### Epic 6 — Artifacts (GCS) + canonical report file (MVP)

- Classes: `GcsUri`, `ArtifactPathPolicy`, `ArtifactStore`, `GcsArtifactStore`, `LLMReportFile`
- Spikes (from `questions/arch_spikes.md`): `SPK-002`, `SPK-012`
- What changes:
  - Детерминированные пути `/<runId>/<timeframe>/<stepId>.json`.
  - Create-only semantics (идемпотентность) и split-brain recovery (reuse existing object).
- Why it matters: идемпотентность, cost control, восстановление после частичных падений.
- Definition of done — local:
  - Unit tests на `ArtifactPathPolicy` (prefix нормализация, валидность GCS URI, стабильность пути).
  - Unit tests на `ArtifactStore.write_bytes_create_only` семантику (AlreadyExists → успех/реюз).
- Definition of done — cloud (dev; requires Epic 0):
  - После успешного run:
    - объект существует в GCS по детерминированному пути,
    - в Firestore записан `outputs.gcs_uri`,
    - повторный триггер не создаёт новый объект (и в логах видно reuse path / no second LLM call при split-brain сценарии).
- Where to test/demo:
  - Local: да (фейковый store).
  - Cloud: да, `dev` (реальный GCS).

### Epic 7 — LLM execution + structured output validation/repair (MVP)

- Classes: `LLMClient`, `GeminiClientAdapter`, `LLMProfile`, `StructuredOutputSpec`, `UserInputAssembler`, `StructuredOutputValidator`, `StructuredOutputInvalid`
- Spikes (from `questions/arch_spikes.md`): `SPK-007`, `SPK-009`, `SPK-010`, `SPK-014`, `SPK-020`
- What changes:
  - Сборка UserInput (scope + артефакты) и вызов Gemini.
  - Детерминированная экстракция JSON, валидация по registry schema, и 0/1 repair попытка по time budget.
- Why it matters: машинно-читаемый результат и предсказуемые ошибки без утечек данных.
- Definition of done — local:
  - Unit tests на `StructuredOutputValidator` с `fixtures/structured_output_invalid/*`:
    - missing required / wrong type / truncated JSON → `INVALID_STRUCTURED_OUTPUT`,
    - диагностика содержит только hash/len + sanitized validation errors (без payload).
  - Unit tests на `UserInputAssembler`:
    - инъекция scope + артефактов, лимиты 64KB/256KB дают `INVALID_STEP_INPUTS`.
  - Контракт: `candidateCount=1` enforced; не происходит markdown-fallback.
- Definition of done — cloud (dev; requires Epic 0):
  - Успешный run делает реальный вызов Gemini и пишет валидный `LLMReportFile`.
  - Негативный сценарий (намеренно плохой schema/prompt/profile) приводит к ожидаемому `error.code`, при этом в Cloud Logging нет raw output/prompt.
- Where to test/demo:
  - Local: да (валидация/сборка/политики с фейковым LLMClient).
  - Cloud: да, `dev` (реальный Gemini endpoint).

### Epic 8 — Invocation orchestration + time budgets (MVP)

- Classes: `CloudEventParser`, `FlowRunEventHandler`, `TimeBudgetPolicy`
- Spikes (from `questions/arch_spikes.md`): `SPK-008`, `SPK-014`, `SPK-015`
- What changes:
  - E2E handler: CloudEvent → load flow_run → select → claim → resolve prompt/schema/context → LLM → write artifact → finalize.
  - Stop-start guard: не начинаем внешние вызовы при `remainingSeconds < finalizeBudgetSeconds`.
- Why it matters: стабильная работа в Cloud Functions gen2 под таймаутами/повторами событий.
- Definition of done — local:
  - E2E unit tests на `FlowRunEventHandler` с фейковыми адаптерами:
    - `cloud_event_ignored` для invalid subject/runId,
    - no-op path (`NO_READY_STEP`, `DEPENDENCY_NOT_SUCCEEDED`),
    - happy path: claim → “LLM” → “GCS” → finalize,
    - time budget path: при `remainingSeconds < finalizeBudgetSeconds` LLM не стартует.
- Definition of done — cloud (dev; requires Epic 0):
  - Полный smoke-run в Cloud:
    - по Firestore update триггерится инвокация,
    - step проходит `READY→RUNNING→SUCCEEDED/FAILED`,
    - артефакт (если успешен) появляется в GCS,
    - в Cloud Logging виден полный execution trace по `jsonPayload.event`.
- Where to test/demo:
  - Local: да (юнит/интеграция на фейках; опционально emulator).
  - Cloud: да, `dev` (реальные Firestore/Eventarc/GCS/Gemini).

## Class allocation (single source of truth for “classes → epics”)

| Class | Epic |
| --- | --- |
| `WorkerConfig` | Epic 1 |
| `GeminiApiKey` | Epic 1 |
| `GeminiAuthConfig` | Epic 1 |
| `EventLogger` | Epic 2 |
| `CloudLoggingEventLogger` | Epic 2 |
| `FlowRun` | Epic 3 |
| `FlowStep` | Epic 3 |
| `LLMReportStep` | Epic 3 |
| `LLMReportInputs` | Epic 3 |
| `ReadyStepSelector` | Epic 3 |
| `StepError` | Epic 3 |
| `ErrorCode` | Epic 3 |
| `FlowRunRepository` | Epic 4 |
| `FirestoreFlowRunRepository` | Epic 4 |
| `ClaimResult` | Epic 4 |
| `FinalizeResult` | Epic 4 |
| `PromptRepository` | Epic 5 |
| `FirestorePromptRepository` | Epic 5 |
| `SchemaRepository` | Epic 5 |
| `FirestoreSchemaRepository` | Epic 5 |
| `LLMPrompt` | Epic 5 |
| `LLMSchema` | Epic 5 |
| `GcsUri` | Epic 6 |
| `ArtifactPathPolicy` | Epic 6 |
| `ArtifactStore` | Epic 6 |
| `GcsArtifactStore` | Epic 6 |
| `LLMReportFile` | Epic 6 |
| `LLMClient` | Epic 7 |
| `GeminiClientAdapter` | Epic 7 |
| `LLMProfile` | Epic 7 |
| `StructuredOutputSpec` | Epic 7 |
| `UserInputAssembler` | Epic 7 |
| `StructuredOutputValidator` | Epic 7 |
| `StructuredOutputInvalid` | Epic 7 |
| `CloudEventParser` | Epic 8 |
| `FlowRunEventHandler` | Epic 8 |
| `TimeBudgetPolicy` | Epic 8 |

## Spike allocation (single source of truth for “spikes → epics”)

| Spike | Epic | Notes |
| --- | --- | --- |
| `SPK-001` | Epic 1 | Done (see decision `#50` in `questions/open_questions.md`) |
| `SPK-002` | Epic 6 | Pending |
| `SPK-003` | Epic 4 | Pending (spec blueprint exists; needs prototype/tests in code) |
| `SPK-004` | Epic 4 | Pending (system-level recovery policy; worker itself is out of scope) |
| `SPK-005` | Epic 4 | Pending |
| `SPK-006` | Epic 5 | Pending |
| `SPK-007` | Epic 1 | Pending (endpoint decision gates auth + SDK feature set) |
| `SPK-008` | Epic 8 | Pending |
| `SPK-009` | Epic 7 | Pending |
| `SPK-010` | Epic 7 | Pending |
| `SPK-011` | Epic 3 | Pending |
| `SPK-012` | Epic 6 | Pending |
| `SPK-013` | Epic 2 | Pending |
| `SPK-014` | Epic 7 | Pending |
| `SPK-015` | Epic 8 | Pending |
| `SPK-016` | Epic 5 | Pending |
| `SPK-017` | Epic 0 | Pending |
| `SPK-018` | Epic 0 | Pending |
| `SPK-019` | Epic 3 | Pending |
| `SPK-020` | Epic 1 | Pending |
