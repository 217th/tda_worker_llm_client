# Handoff checklist

Aggregate the readiness criteria for handing off this component to implementation and QA.

## Documentation pack completeness (minimum)

- `contracts/flow_run.schema.json` is authoritative and referenced by specs
- `spec/implementation_contract.md` describes step selection, claiming, dependencies, and state transitions
- `spec/error_and_retry_model.md` defines retryability and idempotency rules
- `spec/observability.md` defines required log fields and baseline events
- `spec/deploy_and_envs.md` lists required env vars and IAM
- `questions/open_questions.md` is populated and triaged (blockers marked)
- Implementation plan reuses proven code (copy-paste) from `worker_chart_export` and `worker_ohlcv_export` for CloudEvent parsing + structured logging (aligned to this spec pack)

## MVP acceptance checks

- Duplicate Firestore update events do not produce duplicate artifacts
- Two concurrent invocations do not both claim the same step
- Unmet `dependsOn` prevents execution
- LLM output artifact is written and referenced from Firestore
