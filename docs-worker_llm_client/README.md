# docs-worker_llm_client

## Purpose

Document the component/service **as part of a larger multi-service system** so it is ready for:
- architecture and technical design
- epic decomposition and planning

`worker_llm_client` is a Google Cloud Function (gen2) that executes `LLM_REPORT` steps in `flow_runs/{runId}` documents by calling Google Gemini and writing the report artifact to Cloud Storage.

## Quick links

- `spec/implementation_contract.md`
- `spec/architecture_overview.md`
- `spec/system_integration.md`
- `contracts/README.md`
- `questions/open_questions.md`
- `changelog.md`
