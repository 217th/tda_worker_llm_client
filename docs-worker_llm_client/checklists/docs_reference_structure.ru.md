## Эталонная структура каталогов и файлов

Рекомендуемая структура документов для нового компонента:

```text
docs-<component-key>/
  README.md
  plan_wbs.md

  spec/
    implementation_contract.md
    architecture_overview.md
    error_and_retry_model.md
    observability.md
    deploy_and_envs.md
    handoff_checklist.md

  contracts/
    <component>_input.schema.json
    <component>_output.schema.json
    <component>_event_*.schema.json
    error_payload.schema.json
    README.md

  checklists/
    <component>.md
    qa_checklist.md

  test_vectors/
    inputs/
      happy_path_*.json
      invalid_*.json
    outputs/
      expected_*.json
      expected_patches_*.json
    README.md

  fixtures/
    api/
      <provider-1>/
      <provider-2>/
    storage/
      ...
    README.md

  questions/
    open_questions.md
```

Краткое сопоставление с чек-листом:

- **`docs-<component-key>/README.md`**
  - Позиционирование компонента и его границы ответственности.
  - Product‑ценность и связь с глобальными требованиями (`docs-general`, `docs-gcp` и др.).

- **`plan_wbs.md`**
  - Этапность, WBS и инкременты (кандидаты в эпики).
  - Описание ценности по инкрементам и критериев приёмки (связано с блоками про “Естественные инкременты” и “Acceptance‑критерии” чек-листа).

- **`spec/implementation_contract.md`**
  - Доменные сущности и жизненный цикл.
  - Ключевые инварианты.
  - Основные сценарии поведения (чёрный ящик) и high‑level flow.

- **`spec/architecture_overview.md`**
  - Роль компонента в архитектуре.
  - Входящие и исходящие зависимости, общая схема потоков.

- **`spec/error_and_retry_model.md`**
  - Словарь кодов ошибок и их классификация (ретраи/лимиты/фатальные).
  - Идемпотентность и поведение при ретраях.

- **`spec/observability.md`**
  - Минимальный и расширенный контракт логов.
  - Наметки по метрикам, алёртам и дашбордам.

- **`spec/deploy_and_envs.md`**
  - Модель сред и базовая стратегия деплоя.
  - Различия конфигурации по средам, ограничения по сети и offline‑режимы.
  - Smoke‑сценарии, мониторинг раскатки, черновой план отката.

- **`spec/handoff_checklist.md`**
  - Агрегирующий чек-лист для приёмки/передачи компонента (линкует пункты из этого файла и других спек).

- **`contracts/*.schema.json` + `contracts/README.md`**
  - Формальные схемы ключевых данных (входы/выходы/события, error‑payload’ы).
  - Человеческое описание ключевых полей, версионирование.

- **`checklists/<component>.md`, `checklists/qa_checklist.md`**
  - Технический implementation‑чек-лист (контракты, схемы, инварианты, безопасность).
  - QA‑чек-лист: типы тестов, покрытие сценариев, связь с QA‑циклом.

- **`test_vectors/`**
  - Эталонные примеры (happy‑path, ошибки), синхронизированные с `contracts/*.schema.json` и сценариями из `implementation_contract.md`.

- **`fixtures/`**
  - Фикстуры для mock/record‑режимов внешних API/хранилищ (поддержка offline‑CI).

- **`questions/open_questions.md`**
  - Реестр открытых вопросов с пометкой “блокирует/не блокирует” (соответствует блоку про открытые вопросы в чек-листе).

Эту структуру можно адаптировать под конкретный компонент, но при ревью желательно проверять, что все критически необходимые и необходимые пункты чек-листа имеют “своё место” в дереве.
