# T-060: Persist full usageMetadata payload

## Summary

- Store the complete `usageMetadata` object returned by the model in the report output metadata.

## Scope

- Capture all fields from model response `usageMetadata` (including nulls and nested details) without filtering.
- Update contracts/specs to reflect full passthrough behavior.
- Update examples/test vectors to include full usageMetadata payload.
- Add/update unit tests for persistence behavior.

## Plan

1) Docs + contracts
   - Update @docs/spec/implementation_contract.md to state usageMetadata is stored verbatim.
   - Update @docs/contracts/llm_report_file.schema.json to allow arbitrary fields under `usageMetadata`.
   - Update examples/test vectors:
     - @docs/contracts/examples/llm_report_file.example.json
     - @docs/test_vectors/outputs/step_llm_report.succeeded_patch.example.json

2) Implementation
   - Ensure LLM execution path stores usageMetadata as-is in report metadata (no field filtering).
   - Confirm any mapping/conversion in @worker_llm_client/infra/gemini.py or reporting domain preserves full payload.

3) Tests
   - Add/update tests to verify full usageMetadata payload is preserved (including nested details and nulls).

## Risks

- Schema strictness may reject extra fields if not updated.

## Verify Steps

- `python -m pytest tests/test_handler_logging.py -q` (if metadata tested there)
- `python -m pytest tests/test_structured_output.py -q` (if applicable)

## Rollback Plan

- Revert the commit and restore minimal usageMetadata fields.
