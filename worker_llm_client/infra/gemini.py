from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from worker_llm_client.app.llm_client import (
    LLMClient,
    ProviderResponse,
    RateLimited,
    RequestFailed,
    SafetyBlocked,
)
from worker_llm_client.app.services import LLMSchema
from worker_llm_client.reporting.domain import LLMProfile
from worker_llm_client.reporting.services import ChartImage

try:  # pragma: no cover - optional dependency
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors
except Exception:  # pragma: no cover - optional dependency
    genai = None
    types = None
    genai_errors = None


@dataclass(slots=True)
class GeminiClientAdapter(LLMClient):
    api_key: str
    timeout_seconds: int = 600

    def __post_init__(self) -> None:
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ValueError("api_key must be a non-empty string")

    def generate(
        self,
        *,
        system: str,
        user_parts: Sequence[Any],
        profile: LLMProfile,
        llm_schema: LLMSchema | None = None,
    ) -> ProviderResponse:
        if genai is None or types is None:
            raise RequestFailed("google-genai SDK is unavailable")

        provider_request = profile.to_provider_request()
        config = dict(provider_request.get("config", {}))
        response_mime_type = config.get("responseMimeType")
        response_schema = llm_schema.provider_schema() if llm_schema is not None else None

        parts = [_coerce_part(part) for part in user_parts]

        client = genai.Client(api_key=self.api_key)
        try:
            response = client.models.generate_content(
                model=profile.model_name,
                contents=parts,
                config=types.GenerateContentConfig(
                    systemInstruction=system,
                    temperature=config.get("temperature"),
                    topP=config.get("topP"),
                    topK=config.get("topK"),
                    maxOutputTokens=config.get("maxOutputTokens"),
                    candidateCount=config.get("candidateCount"),
                    stopSequences=config.get("stopSequences"),
                    responseMimeType=response_mime_type,
                    responseJsonSchema=response_schema,
                    thinkingConfig=config.get("thinkingConfig"),
                ),
            )
        except Exception as exc:
            raise _map_gemini_error(exc) from exc

        text = getattr(response, "text", None)
        if text is None:
            text = _extract_text(response)

        usage = _extract_usage(response)
        finish_reason = _extract_finish_reason(response)

        return ProviderResponse(
            text=text,
            finish_reason=finish_reason,
            usage=usage,
            raw=response,
        )


def _extract_text(response: Any) -> str | None:
    candidates = getattr(response, "candidates", None)
    if not isinstance(candidates, Sequence) or not candidates:
        return None
    candidate = candidates[0]
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None)
    if not isinstance(parts, Sequence):
        return None
    texts = [part.text for part in parts if getattr(part, "text", None)]
    return "".join(texts) if texts else None


def _extract_finish_reason(response: Any) -> str | None:
    candidates = getattr(response, "candidates", None)
    if not isinstance(candidates, Sequence) or not candidates:
        return None
    return getattr(candidates[0], "finish_reason", None)


def _extract_usage(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        try:
            return usage.model_dump(exclude_none=False, by_alias=True)
        except TypeError:
            return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return None


def _coerce_part(part: Any) -> Any:
    if types is None:
        return part
    if isinstance(part, ChartImage):
        return types.Part.from_bytes(data=part.data, mime_type=part.mime_type)
    if hasattr(part, "data") and hasattr(part, "mime_type"):
        data = getattr(part, "data")
        mime_type = getattr(part, "mime_type")
        if isinstance(data, (bytes, bytearray)) and isinstance(mime_type, str):
            return types.Part.from_bytes(data=bytes(data), mime_type=mime_type)
    if isinstance(part, (bytes, bytearray)):
        raise RequestFailed("image bytes require mime_type")
    if isinstance(part, str):
        return types.Part.from_text(text=part)
    return part


def _map_gemini_error(exc: Exception) -> Exception:
    if genai_errors is not None and isinstance(exc, genai_errors.APIError):
        status = getattr(exc, "status", None)
        code = getattr(exc, "code", None)
        if code == 429 or status == "RESOURCE_EXHAUSTED":
            return RateLimited("Gemini rate limited")
        if getattr(exc, "status", None) == "SAFETY":
            return SafetyBlocked("Gemini safety block")
        if 500 <= int(code or 0) < 600:
            return RequestFailed("Gemini server error")
        return RequestFailed("Gemini request failed")
    return RequestFailed("Gemini request failed")
