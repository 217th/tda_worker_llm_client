# docs

## Purpose

Document the component/service **as part of a larger multi-service system** so it is ready for:
- architecture and technical design
- epic decomposition and planning

`worker_llm_client` is a Google Cloud Function (gen2) that executes `LLM_REPORT` steps in `flow_runs/{runId}` documents by calling Google Gemini and writing the report artifact to Cloud Storage.

## Quick links

- `spec/implementation_contract.md`
- `spec/architecture_overview.md`
- `spec/system_integration.md`
- `spec/prompt_storage_and_context.md`
- `static_model.md`
- `contracts/README.md`
- `questions/open_questions.md`
- `changelog.md`

## Project tree (annotated)

This tree lists the source-of-truth docs for the component. Notes:
- `inbox/` is **append-only raw intake** and is not the source of truth; main specs/contracts must not depend on inbox artifacts.
- `contracts/` are the source of truth for machine-readable shapes; `spec/` explains behavior and integration.

```text
docs/
  README.md — This entrypoint; quick links + how to read the pack.
  changelog.md — Per-iteration changelog for this docs pack.
  plan_wbs.md — Epic-level plan/WBS aligned with `static_model.md`.
  static_model.md — Proposed MVP code structure (contexts/modules/classes) for implementation.

  checklists/
    README.md — Checklist usage notes.
    component_docs_checklist.ru.md — Readiness checklist for a component spec pack (ru).
    docs_reference_structure.ru.md — Recommended docs structure reference (ru).

  contracts/
    README.md — Index of contracts + examples in this folder.
    flow_run.schema.json — Canonical JSON Schema for Firestore `flow_runs/{runId}` (worker-facing subset).
    flow_run.md — Human-readable semantics for `flow_runs/{runId}` fields and step lifecycle.
    llm_prompt.schema.json — Canonical JSON Schema for Firestore `llm_prompts/{promptId}`.
    llm_prompt.md — Notes for prompt docs (versioning, UserInput assembly expectations).
    llm_schema.schema.json — Canonical JSON Schema for Firestore `llm_schemas/{schemaId}` (structured output schema registry).
    llm_schema.md — Schema registry rules (immutability, naming, minimal invariants, debugging).
    llm_report_file.schema.json — Canonical JSON Schema for the GCS report artifact file (`LLMReportFile`).

    debug/
      llm_report_output.debug.schema.json — Debug-only schema for model-owned `output` derived from the `so_schema.md` example payload.

    examples/
      flow_run.example.json — Example `flow_runs/{runId}` document.
      llm_prompt.example.json — Example `llm_prompts/{promptId}` document.
      llm_schema.example.json — Example `llm_schemas/{schemaId}` document.
      llm_report_file.example.json — Example GCS report artifact (`LLMReportFile`).

  fixtures/
    README.md — What fixtures are and how they differ from test vectors.
    structured_output_invalid/
      truncated_json.txt — Invalid/truncated model output payload fixture.
      missing_required.json — Missing required field fixture (e.g. `summary.markdown`).
      wrong_type.json — Wrong type fixture (e.g. `summary.markdown` not a string).

  questions/
    open_questions.md — Open questions (must be kept current; close with dated decisions).
    arch_spikes.md — Backlog of architectural spikes (research/prototype tasks).

  spec/
    architecture_overview.md — High-level role of the worker, dependencies, and flow.
    system_integration.md — System context, contracts, and integration points (Firestore/GCS/Gemini).
    implementation_contract.md — Black-box behavior contract: selection/claim/finalize, structured output, time budgets.
    error_and_retry_model.md — Error taxonomy, retry/backoff, idempotency patterns.
    observability.md — Logging envelope + event taxonomy + required fields.
    prompt_storage_and_context.md — Prompt storage, UserInput assembly, and context injection rules.
    deploy_and_envs.md — Deployment model and environment configuration (env vars/IAM).
    handoff_checklist.md — Readiness checklist for implementation/QA handoff.

  test_vectors/
    README.md — Conventions for inputs/outputs test vectors.
    inputs/
      flow_run.ready_llm_report.json — Ready-to-run flow_run example input (happy path).
      flow_run.ready_llm_report_missing_prompt.json — Input example where prompt doc is missing.
    outputs/
      step_llm_report.succeeded_patch.example.json — Expected Firestore patch on success.
      step_llm_report.failed_invalid_structured_output.truncated_json.patch.example.json — Expected patch on truncated JSON.
      step_llm_report.failed_invalid_structured_output.missing_required.patch.example.json — Expected patch on missing required field.
      step_llm_report.failed_invalid_structured_output.wrong_type.patch.example.json — Expected patch on wrong type.
```

## Recommended reading order (system architect)

If I were approaching this as a system architect, I would read in this order:

1) `spec/architecture_overview.md` — fastest way to align on boundaries and runtime.
2) `spec/system_integration.md` — upstream/downstream interfaces + contracts.
3) `spec/implementation_contract.md` — authoritative black-box behavior and invariants.
4) `spec/error_and_retry_model.md` — failure modes, idempotency, retry boundaries.
5) `spec/observability.md` — what we can reliably see/alert on in production.
6) `spec/prompt_storage_and_context.md` — prompt/schema sources of truth + context injection.
7) `contracts/README.md` + key schemas in `contracts/` — machine-checkable shapes used by the system.
8) `test_vectors/README.md` + `test_vectors/**` + `fixtures/**` — concrete examples of happy/edge paths.
9) `spec/deploy_and_envs.md` — deployment assumptions and required configuration.
10) `spec/handoff_checklist.md` + `plan_wbs.md` + `static_model.md` — readiness + execution plan + implementation structure.
11) `questions/open_questions.md` + `changelog.md` — remaining decisions and history of changes.
12) `questions/arch_spikes.md` — research backlog and spikes to schedule.
