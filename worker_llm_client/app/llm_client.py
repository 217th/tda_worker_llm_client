from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from worker_llm_client.app.services import LLMSchema
from worker_llm_client.reporting.domain import LLMProfile


class LLMClientError(RuntimeError):
    """Base error for LLM client failures."""


class RateLimited(LLMClientError):
    """Raised when provider returns a rate limit response."""


class RequestFailed(LLMClientError):
    """Raised when provider call fails with a retryable error."""


class SafetyBlocked(LLMClientError):
    """Raised when provider blocks output for safety."""


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    text: str | None
    finish_reason: str | None
    usage: dict[str, Any] | None
    raw: Any


class LLMClient(Protocol):
    def generate(
        self,
        *,
        system: str,
        user_parts: Sequence[Any],
        profile: LLMProfile,
        llm_schema: LLMSchema | None = None,
    ) -> ProviderResponse:
        ...
