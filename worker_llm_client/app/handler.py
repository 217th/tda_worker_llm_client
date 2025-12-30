from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

from worker_llm_client.app.services import (
    FlowRunRepository,
    PromptRepository,
    SchemaRepository,
    build_step_update,
)
from worker_llm_client.artifacts.domain import ArtifactPathPolicy, InvalidIdentifier
from worker_llm_client.artifacts.services import ArtifactStore, ArtifactWriteFailed
from worker_llm_client.ops.logging import EventLogger, MAX_ARRAY_LENGTH
from worker_llm_client.reporting.domain import LLMReportFile, SerializationError
from worker_llm_client.workflow.domain import ErrorCode, InvalidStepInputs, LLMProfileInvalid
from worker_llm_client.workflow.policies import ReadyStepSelector


def _extract_field(cloud_event: Any, name: str) -> Any:
    if hasattr(cloud_event, "get"):
        try:
            return cloud_event.get(name)
        except Exception:
            return None
    return getattr(cloud_event, name, None)


def _parse_run_id(subject: Any, flow_runs_collection: str) -> str | None:
    if not isinstance(subject, str) or not subject.strip():
        return None
    parts = [part for part in subject.split("/") if part]
    for idx, part in enumerate(parts):
        if part == flow_runs_collection and idx + 1 < len(parts):
            run_id = parts[idx + 1].strip()
            return run_id or None
    return None


def _step_summaries(steps: list[Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for step in steps[:MAX_ARRAY_LENGTH]:
        summaries.append(
            {
                "stepId": step.step_id,
                "stepType": step.step_type,
                "status": step.status,
                "dependsOn": list(step.depends_on),
            }
        )
    return summaries


_SCHEMA_VERSION_RE = re.compile(r"^llm_report_output_v([1-9][0-9]*)$")


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_schema_version(schema_id: str) -> int | None:
    if not isinstance(schema_id, str):
        return None
    match = _SCHEMA_VERSION_RE.fullmatch(schema_id.strip())
    if not match:
        return None
    return int(match.group(1))


def _extract_symbol(flow_run: Any) -> str | None:
    raw = getattr(flow_run, "raw", None)
    if not isinstance(raw, Mapping):
        return None
    scope = raw.get("scope")
    if not isinstance(scope, Mapping):
        return None
    symbol = scope.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        return None
    return symbol.strip()


def _extract_timeframe(step: Any) -> str | None:
    raw = getattr(step, "raw", None)
    if not isinstance(raw, Mapping):
        return None
    timeframe = raw.get("timeframe")
    if not isinstance(timeframe, str) or not timeframe.strip():
        return None
    return timeframe.strip()


def _extract_model_name(llm_profile: Mapping[str, Any]) -> str:
    model_name = llm_profile.get("modelName")
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    model_name = llm_profile.get("model")
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    return "dry_run"


def handle_cloud_event(
    cloud_event: Any,
    *,
    flow_repo: FlowRunRepository,
    prompt_repo: PromptRepository,
    schema_repo: SchemaRepository,
    event_logger: EventLogger,
    flow_runs_collection: str,
    artifact_store: ArtifactStore | None = None,
    path_policy: ArtifactPathPolicy | None = None,
    artifacts_dry_run: bool = False,
) -> str:
    event_id = _extract_field(cloud_event, "id") or "unknown"
    event_type = _extract_field(cloud_event, "type") or "unknown"
    subject = _extract_field(cloud_event, "subject") or "unknown"

    event_logger.log(
        event="cloud_event_received",
        severity="INFO",
        eventId=event_id,
        runId="unknown",
        stepId="unknown",
        eventType=event_type,
        subject=subject,
    )

    run_id = _parse_run_id(subject, flow_runs_collection)
    if run_id is None:
        event_logger.log(
            event="cloud_event_ignored",
            severity="WARNING",
            eventId=event_id,
            runId="unknown",
            stepId="unknown",
            reason="invalid_subject",
        )
        return "ignored"

    record = flow_repo.get(run_id)
    if record is None:
        event_logger.log(
            event="cloud_event_ignored",
            severity="WARNING",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            reason="flow_run_not_found",
        )
        return "ignored"

    flow_run = record.flow_run
    event_logger.log(
        event="cloud_event_parsed",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId="unknown",
        flowRunFound=True,
        flowRunStatus=flow_run.status,
        flowRunSteps=_step_summaries(flow_run.iter_steps_sorted()),
    )

    if flow_run.is_terminal():
        event_logger.log(
            event="cloud_event_noop",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            reason="already_final",
        )
        event_logger.log(
            event="cloud_event_finished",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            status="noop",
        )
        return "noop"

    pick = ReadyStepSelector.pick(flow_run)
    if pick.step is None:
        event_logger.log(
            event="cloud_event_noop",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            reason=pick.reason or "no_ready_step",
        )
        event_logger.log(
            event="cloud_event_finished",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            status="noop",
        )
        return "noop"

    step = pick.step.step
    step_id = step.step_id
    timeframe = step.raw.get("timeframe") if isinstance(step.raw, Mapping) else None
    event_logger.log(
        event="ready_step_selected",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        stepType=step.step_type,
        timeframe=timeframe,
    )

    try:
        inputs = pick.step.parse_inputs(flow_run=flow_run)
    except (InvalidStepInputs, LLMProfileInvalid) as exc:
        code = (
            ErrorCode.INVALID_STEP_INPUTS
            if isinstance(exc, InvalidStepInputs)
            else ErrorCode.LLM_PROFILE_INVALID
        )
        event_logger.log(
            event="cloud_event_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            status="failed",
            error={"code": code.value, "message": str(exc)},
        )
        return "failed"

    event_logger.log(
        event="prompt_fetch_started",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        llm={"promptId": inputs.prompt_id},
    )

    prompt = prompt_repo.get(inputs.prompt_id)
    if prompt is None:
        event_logger.log(
            event="prompt_fetch_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            ok=False,
            error={"code": ErrorCode.PROMPT_NOT_FOUND.value},
        )
        event_logger.log(
            event="cloud_event_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            status="failed",
        )
        return "prompt_not_found"

    event_logger.log(
        event="prompt_fetch_finished",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        ok=True,
    )

    structured_output = (
        inputs.llm_profile.get("structuredOutput")
        if isinstance(inputs.llm_profile, Mapping)
        else None
    )
    schema_id = None
    if isinstance(structured_output, Mapping):
        schema_id = structured_output.get("schemaId")

    if not isinstance(schema_id, str) or not schema_id.strip():
        event_logger.log(
            event="structured_output_schema_invalid",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            llm={"schemaId": schema_id or "unknown"},
            reason={"message": "schemaId missing in llmProfile"},
            error={"code": ErrorCode.LLM_PROFILE_INVALID.value},
        )
        event_logger.log(
            event="cloud_event_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            status="failed",
        )
        return "schema_invalid"

    schema = schema_repo.get(schema_id)
    if schema is None:
        event_logger.log(
            event="structured_output_schema_invalid",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            llm={"schemaId": schema_id},
            reason={"message": "schema missing or violates invariants"},
            error={"code": ErrorCode.LLM_PROFILE_INVALID.value},
        )
        event_logger.log(
            event="cloud_event_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            status="failed",
        )
        return "schema_invalid"

    if artifacts_dry_run:
        if artifact_store is None or path_policy is None:
            event_logger.log(
                event="cloud_event_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                status="failed",
                error={
                    "code": ErrorCode.GCS_WRITE_FAILED.value,
                    "message": "Artifact store unavailable for dry-run",
                },
            )
            return "failed"

        schema_version = _parse_schema_version(schema.schema_id)
        if schema_version is None:
            event_logger.log(
                event="structured_output_schema_invalid",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                llm={"schemaId": schema.schema_id, "schemaSha256": schema.sha256},
                reason={"message": "schemaId must follow llm_report_output_v{N}"},
                error={"code": ErrorCode.LLM_PROFILE_INVALID.value},
            )
            event_logger.log(
                event="cloud_event_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                status="failed",
                error={
                    "code": ErrorCode.LLM_PROFILE_INVALID.value,
                    "message": "Invalid schemaId format",
                },
            )
            return "failed"

        timeframe = _extract_timeframe(step)
        symbol = _extract_symbol(flow_run)
        if timeframe is None or symbol is None:
            event_logger.log(
                event="cloud_event_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                status="failed",
                error={
                    "code": ErrorCode.INVALID_STEP_INPUTS.value,
                    "message": "Missing timeframe or scope.symbol",
                },
            )
            return "failed"

        try:
            report_uri = path_policy.report_uri(run_id, timeframe, step_id)
        except InvalidIdentifier as exc:
            event_logger.log(
                event="cloud_event_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                status="failed",
                error={
                    "code": ErrorCode.INVALID_STEP_INPUTS.value,
                    "message": str(exc),
                },
            )
            return "failed"

        llm_profile = (
            dict(inputs.llm_profile) if isinstance(inputs.llm_profile, Mapping) else {}
        )
        model_name = _extract_model_name(llm_profile)
        created_at = _now_rfc3339()
        metadata: dict[str, Any] = {
            "schemaVersion": schema_version,
            "runId": run_id,
            "stepId": step_id,
            "createdAt": created_at,
            "finishedAt": created_at,
            "symbol": symbol,
            "timeframe": timeframe,
            "llm": {
                "promptId": inputs.prompt_id,
                "modelName": model_name,
                "schemaId": schema.schema_id,
                "schemaSha256": schema.sha256,
                "llmProfile": llm_profile,
                "finishReason": "DRY_RUN",
            },
            "inputs": {
                "ohlcv_gcs_uri": inputs.ohlcv_gcs_uri,
                "charts_outputsManifestGcsUri": inputs.charts_manifest_gcs_uri,
            },
        }
        if inputs.previous_report_gcs_uris:
            metadata["inputs"]["report_gcs_uris"] = list(inputs.previous_report_gcs_uris)

        report = LLMReportFile(
            metadata=metadata,
            output={
                "summary": {"markdown": "DRY_RUN"},
                "details": {},
            },
        )
        try:
            payload = report.to_json_bytes()
        except SerializationError as exc:
            event_logger.log(
                event="cloud_event_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                status="failed",
                error={
                    "code": ErrorCode.INVALID_STEP_INPUTS.value,
                    "message": str(exc),
                },
            )
            return "failed"

        payload_bytes = len(payload)
        event_logger.log(
            event="gcs_write_started",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            artifact={"gcs_uri": str(report_uri)},
            bytes=payload_bytes,
        )

        try:
            write_result = artifact_store.write_bytes_create_only(
                report_uri, payload, content_type="application/json"
            )
        except ArtifactWriteFailed as exc:
            event_logger.log(
                event="gcs_write_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                artifact={"gcs_uri": str(report_uri)},
                ok=False,
                bytes=payload_bytes,
                error={"code": ErrorCode.GCS_WRITE_FAILED.value, "retryable": exc.retryable},
            )
            event_logger.log(
                event="cloud_event_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                status="failed",
                error={
                    "code": ErrorCode.GCS_WRITE_FAILED.value,
                    "message": "Artifact write failed",
                },
            )
            return "failed"

        event_logger.log(
            event="gcs_write_finished",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            artifact={"gcs_uri": str(report_uri)},
            ok=True,
            bytes=payload_bytes,
            reused=write_result.reused,
        )

        patch = build_step_update(step_id, {"outputs.gcs_uri": str(report_uri)})
        try:
            flow_repo.patch(run_id, patch, precondition_update_time=record.update_time)
        except Exception:
            event_logger.log(
                event="cloud_event_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                status="failed",
                error={
                    "code": ErrorCode.FIRESTORE_FINALIZE_FAILED.value,
                    "message": "Failed to update outputs.gcs_uri",
                },
            )
            return "failed"

        event_logger.log(
            event="cloud_event_finished",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            status="ok",
        )
        return "ok"
    event_logger.log(
        event="cloud_event_finished",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        status="ok",
    )
    return "ok"
