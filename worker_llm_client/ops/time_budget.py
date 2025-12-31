"""Time budget policy for invocation guardrails."""

from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True, slots=True)
class TimeBudgetPolicy:
    """Tracks remaining invocation time and guards external calls."""

    invocation_started_at: float
    invocation_timeout_seconds: int
    finalize_budget_seconds: int

    @classmethod
    def start_now(
        cls, *, invocation_timeout_seconds: int, finalize_budget_seconds: int
    ) -> "TimeBudgetPolicy":
        return cls(
            invocation_started_at=time.monotonic(),
            invocation_timeout_seconds=invocation_timeout_seconds,
            finalize_budget_seconds=finalize_budget_seconds,
        )

    def remaining_seconds(self, now: float | None = None) -> float:
        if now is None:
            now = time.monotonic()
        elapsed = max(0.0, now - self.invocation_started_at)
        remaining = self.invocation_timeout_seconds - elapsed
        return remaining if remaining > 0 else 0.0

    def can_start_llm_call(self, now: float | None = None) -> bool:
        return self.remaining_seconds(now) >= self.finalize_budget_seconds

    def can_start_repair_call(self, now: float | None = None) -> bool:
        return self.remaining_seconds(now) >= self.finalize_budget_seconds

    def snapshot(self, now: float | None = None) -> dict[str, float]:
        return {
            "remainingSeconds": self.remaining_seconds(now),
            "finalizeBudgetSeconds": float(self.finalize_budget_seconds),
        }
