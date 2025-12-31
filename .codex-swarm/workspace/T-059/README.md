# T-059: Support external previous report references

## Summary

- Add support for previous report inputs by explicit GCS URI (cross-workflow), with clear precedence rules.

## Scope

- Extend LLM_REPORT inputs to accept previous report references by `gcs_uri` (external) in addition to existing `previousReportStepIds` (same-workflow).
- Precedence: if both `stepId` and `gcs_uri` are provided for a reference, use `gcs_uri`.
- Validation: invalid references must fail with `INVALID_STEP_INPUTS`.
- Update contracts/docs in `docs/`.
- Add/update unit tests for parsing, resolution, and validation.

## Plan

1) Contract + docs update
   - Define input shape for external previous report references (proposed: `inputs.previousReports[]` objects with optional `stepId` and `gcs_uri`).
   - Preserve backward compatibility: `previousReportStepIds` remains supported.
   - Update docs:
     - @docs/contracts/flow_run.md (new field + precedence rules).
     - @docs/contracts/flow_run.schema.json (schema for new field).
     - @docs/spec/implementation_contract.md + @docs/spec/prompt_storage_and_context.md (resolution rules and failure cases).
     - @docs/contracts/examples/flow_run.example.json (example usage).

2) Implementation changes
   - Parse new field into `LLMReportInputs` in @worker_llm_client/workflow/domain.py.
   - Resolve previous report URIs:
     - If `gcs_uri` present → use directly (validate format).
     - Else resolve `stepId` to `outputs.gcs_uri` (require LLM_REPORT).
     - If neither present → `INVALID_STEP_INPUTS`.
   - Merge with existing `previousReportStepIds` logic for backward compatibility.
   - Ensure logging and metadata include the final list of report URIs.

3) Tests
   - Update @tests/test_workflow_domain.py for:
     - `previousReports` with `gcs_uri` only.
     - `previousReports` with `stepId` only.
     - Both fields → prefer `gcs_uri`.
     - Invalid references → `INVALID_STEP_INPUTS`.
     - Legacy `previousReportStepIds` still works.
   - Update @tests/test_user_input_assembler.py to accept external reports.
   - Add logging assertions if needed (@tests/test_handler_logging.py).

## Risks

- Contract change could break existing clients if not backward-compatible.

## Verify Steps

- `python -m pytest tests/test_workflow_domain.py -q`
- `python -m pytest tests/test_user_input_assembler.py -q`
- `python -m pytest tests/test_handler_logging.py -q` (if touched)

## Rollback Plan

- Revert the commit and remove new input field from docs.
