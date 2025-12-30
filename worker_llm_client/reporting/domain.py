from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Sequence

from worker_llm_client.workflow.domain import LLMProfileInvalid


class SerializationError(ValueError):
    """Raised when report serialization fails unexpectedly."""


_SCHEMA_ID_RE = re.compile(r"^llm_report_output_v([1-9][0-9]*)$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class StructuredOutputSpec:
    schema_id: str
    kind: str = "LLM_REPORT_OUTPUT"
    schema_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.schema_id, str) or not self.schema_id.strip():
            raise LLMProfileInvalid("structuredOutput.schemaId is required")
        if self.kind != "LLM_REPORT_OUTPUT":
            raise LLMProfileInvalid("structuredOutput.kind must be LLM_REPORT_OUTPUT")
        if self.schema_sha256 is not None:
            if not isinstance(self.schema_sha256, str) or not _SHA256_RE.fullmatch(
                self.schema_sha256
            ):
                raise LLMProfileInvalid("structuredOutput.schemaSha256 must be hex sha256")

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> "StructuredOutputSpec":
        if not isinstance(raw, Mapping):
            raise LLMProfileInvalid("llmProfile.structuredOutput must be an object")
        schema_id = raw.get("schemaId")
        kind = raw.get("kind") or "LLM_REPORT_OUTPUT"
        schema_sha256 = raw.get("schemaSha256")
        return cls(schema_id=schema_id, kind=kind, schema_sha256=schema_sha256)

    def schema_version(self) -> int:
        match = _SCHEMA_ID_RE.fullmatch(self.schema_id)
        if not match:
            raise LLMProfileInvalid("structuredOutput.schemaId must follow llm_report_output_v{N}")
        return int(match.group(1))

    def to_dict(self) -> dict[str, Any]:
        payload = {"schemaId": self.schema_id, "kind": self.kind}
        if self.schema_sha256:
            payload["schemaSha256"] = self.schema_sha256
        return payload


@dataclass(frozen=True, slots=True)
class LLMProfile:
    model_name: str
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_output_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()
    candidate_count: int | None = None
    response_mime_type: str | None = None
    structured_output: StructuredOutputSpec | None = None
    thinking_config: Mapping[str, Any] | None = None
    raw: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise LLMProfileInvalid("llmProfile.modelName (or model) is required")

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> "LLMProfile":
        if not isinstance(raw, Mapping):
            raise LLMProfileInvalid("llmProfile must be an object")

        model_name = _coalesce_model_name(raw)

        temperature = _optional_number(raw.get("temperature"), label="llmProfile.temperature")
        top_p = _optional_number(raw.get("topP"), label="llmProfile.topP")
        top_k = _optional_int(raw.get("topK"), label="llmProfile.topK")
        max_output_tokens = _optional_int(
            raw.get("maxOutputTokens"), label="llmProfile.maxOutputTokens"
        )
        stop_sequences = _optional_str_array(
            raw.get("stopSequences"), label="llmProfile.stopSequences"
        )
        candidate_count = _optional_int(
            raw.get("candidateCount"), label="llmProfile.candidateCount"
        )
        response_mime_type = raw.get("responseMimeType")
        if response_mime_type is not None and (
            not isinstance(response_mime_type, str) or not response_mime_type.strip()
        ):
            raise LLMProfileInvalid("llmProfile.responseMimeType must be a string")

        structured_output = None
        if "structuredOutput" in raw:
            structured_output = StructuredOutputSpec.from_raw(raw.get("structuredOutput"))

        thinking_config = raw.get("thinkingConfig")
        if thinking_config is not None and not isinstance(thinking_config, Mapping):
            raise LLMProfileInvalid("llmProfile.thinkingConfig must be an object")

        return cls(
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            stop_sequences=stop_sequences,
            candidate_count=candidate_count,
            response_mime_type=response_mime_type.strip()
            if isinstance(response_mime_type, str)
            else None,
            structured_output=structured_output,
            thinking_config=thinking_config,
            raw=raw,
        )

    def validate_for_mvp(self) -> None:
        if self.response_mime_type != "application/json":
            raise LLMProfileInvalid("llmProfile.responseMimeType must be application/json")
        if self.candidate_count is not None and self.candidate_count != 1:
            raise LLMProfileInvalid("llmProfile.candidateCount must be 1")
        if self.structured_output is None:
            raise LLMProfileInvalid("llmProfile.structuredOutput is required")
        _ = self.structured_output.schema_version()

    def to_provider_request(self) -> dict[str, Any]:
        config: dict[str, Any] = {}
        if self.temperature is not None:
            config["temperature"] = self.temperature
        if self.top_p is not None:
            config["top_p"] = self.top_p
        if self.top_k is not None:
            config["top_k"] = self.top_k
        if self.max_output_tokens is not None:
            config["max_output_tokens"] = self.max_output_tokens
        if self.stop_sequences:
            config["stop_sequences"] = list(self.stop_sequences)
        if self.candidate_count is not None:
            config["candidate_count"] = self.candidate_count
        if self.response_mime_type:
            config["response_mime_type"] = self.response_mime_type
        if self.thinking_config is not None:
            config["thinking_config"] = dict(self.thinking_config)
        return {"model": self.model_name, "config": config}


def _coalesce_model_name(raw: Mapping[str, Any]) -> str:
    model_name = raw.get("modelName")
    model_alias = raw.get("model")
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    if isinstance(model_alias, str) and model_alias.strip():
        return model_alias.strip()
    raise LLMProfileInvalid("llmProfile.modelName (or model) is required")


def _optional_number(value: Any, *, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raise LLMProfileInvalid(f"{label} must be a number")


def _optional_int(value: Any, *, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise LLMProfileInvalid(f"{label} must be an integer")


def _optional_str_array(value: Any, *, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise LLMProfileInvalid(f"{label} must be an array of strings")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise LLMProfileInvalid(f"{label} must contain non-empty strings")
        items.append(item.strip())
    return tuple(items)


@dataclass(frozen=True, slots=True)
class LLMReportFile:
    metadata: Mapping[str, Any]
    output: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": dict(self.metadata),
            "output": dict(self.output),
        }

    def to_json_bytes(self) -> bytes:
        try:
            payload = json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise SerializationError("Failed to serialize LLMReportFile") from exc
        return payload.encode("utf-8")


@dataclass(frozen=True, slots=True)
class StructuredOutputInvalid:
    kind: str
    message: str
    text_bytes: int
    text_sha256: str
    finish_reason: str | None = None

    def to_error_message(self) -> str:
        parts = [f"structured_output_invalid kind={self.kind}"]
        if self.message:
            parts.append(self.message)
        if self.finish_reason and "finishReason=" not in self.message:
            parts.append(f"finishReason={self.finish_reason}")
        return " ".join(parts)
