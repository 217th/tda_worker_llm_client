from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from worker_llm_client.workflow.domain import FlowRun, FlowStep, LLMReportStep, StepInvalid


@dataclass(frozen=True, slots=True)
class BlockedDependency:
    step_id: str
    status: str


@dataclass(frozen=True, slots=True)
class BlockedStep:
    step_id: str
    unmet: tuple[BlockedDependency, ...]


@dataclass(frozen=True, slots=True)
class ReadyStepPick:
    step: LLMReportStep | None
    reason: str | None
    blocked: tuple[BlockedStep, ...] = ()


class ReadyStepSelector:
    """Deterministically select one executable READY LLM_REPORT step."""

    @staticmethod
    def select_executable_llm_step(flow_run: FlowRun) -> LLMReportStep | None:
        return ReadyStepSelector.pick(flow_run).step

    @staticmethod
    def pick(flow_run: FlowRun) -> ReadyStepPick:
        if flow_run.status != "RUNNING":
            return ReadyStepPick(step=None, reason="no_ready_step")

        blocked: list[BlockedStep] = []
        for step in flow_run.iter_steps_sorted():
            if step.step_type != "LLM_REPORT":
                continue
            if step.status != "READY":
                continue
            unmet = _find_unmet_dependencies(flow_run, step)
            if unmet:
                blocked.append(BlockedStep(step_id=step.step_id, unmet=tuple(unmet)))
                continue
            try:
                return ReadyStepPick(step=LLMReportStep.from_flow_step(step), reason=None, blocked=tuple(blocked))
            except StepInvalid:
                continue

        if blocked:
            return ReadyStepPick(step=None, reason="dependency_not_succeeded", blocked=tuple(blocked))
        return ReadyStepPick(step=None, reason="no_ready_step")


def _find_unmet_dependencies(flow_run: FlowRun, step: FlowStep) -> list[BlockedDependency]:
    unmet: list[BlockedDependency] = []
    for dep_id in step.depends_on:
        dep = flow_run.get_step(dep_id)
        if dep is None:
            unmet.append(BlockedDependency(step_id=dep_id, status="MISSING"))
            continue
        if dep.status != "SUCCEEDED":
            unmet.append(BlockedDependency(step_id=dep_id, status=dep.status))
    return unmet
