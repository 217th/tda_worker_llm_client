from __future__ import annotations

from typing import Any, Mapping

from worker_llm_client.app.services import FlowRunRepository, PromptRepository
from worker_llm_client.ops.logging import EventLogger, MAX_ARRAY_LENGTH
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


def handle_cloud_event(
    cloud_event: Any,
    *,
    flow_repo: FlowRunRepository,
    prompt_repo: PromptRepository,
    event_logger: EventLogger,
    flow_runs_collection: str,
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
    event_logger.log(
        event="cloud_event_finished",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        status="ok",
    )
    return "ok"
