from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from worker_llm_client.app.services import LLMSchema
from worker_llm_client.reporting.domain import StructuredOutputInvalid

try:  # pragma: no cover - optional dependency for full JSON Schema validation
    import jsonschema
except Exception:  # pragma: no cover - optional dependency
    jsonschema = None


_REQUIRED_PROP_RE = re.compile(r"'(.+)' is a required property")


@dataclass(frozen=True, slots=True)
class ExtractedText:
    text: str
    method: str


class StructuredOutputValidator:
    def extract_text(self, response: Any) -> ExtractedText:
        if isinstance(response, str):
            return ExtractedText(text=response, method="raw")
        text = getattr(response, "text", None)
        if isinstance(text, str) and text:
            return ExtractedText(text=text, method="response.text")

        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, Sequence) and candidates:
            candidate = candidates[0]
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None)
            if isinstance(parts, Sequence):
                texts = [part.text for part in parts if hasattr(part, "text") and part.text]
                if texts:
                    return ExtractedText(
                        text="".join(texts), method="candidates[0].content.parts"
                    )

        raise ValueError("structured output text missing")

    def validate(
        self,
        *,
        text: str | None,
        llm_schema: LLMSchema,
        finish_reason: str | None = None,
    ) -> dict[str, Any] | StructuredOutputInvalid:
        text_bytes, text_sha = _text_diagnostics(text)
        if text is None or not isinstance(text, str) or not text.strip():
            return StructuredOutputInvalid(
                kind="missing_text",
                message="",
                finish_reason=finish_reason,
                text_bytes=text_bytes,
                text_sha256=text_sha,
            )

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return StructuredOutputInvalid(
                kind="json_parse",
                message="",
                finish_reason=finish_reason,
                text_bytes=text_bytes,
                text_sha256=text_sha,
            )

        error = _validate_payload(payload, llm_schema.json_schema)
        if error:
            return StructuredOutputInvalid(
                kind="schema_validation",
                message=error,
                finish_reason=None,
                text_bytes=text_bytes,
                text_sha256=text_sha,
            )

        return payload


def _text_diagnostics(text: str | None) -> tuple[int, str]:
    raw = text.encode("utf-8") if isinstance(text, str) else b""
    return len(raw), hashlib.sha256(raw).hexdigest()


def _validate_payload(payload: Any, schema: Mapping[str, Any]) -> str | None:
    if jsonschema is not None:
        return _validate_with_jsonschema(payload, schema)
    return _validate_minimal(payload)


def _validate_with_jsonschema(payload: Any, schema: Mapping[str, Any]) -> str | None:
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if not errors:
        return None
    return _format_jsonschema_error(errors[0])


def _format_jsonschema_error(error: Any) -> str:
    validator = getattr(error, "validator", None)
    path = _format_path(getattr(error, "path", ()))

    if validator == "required":
        missing = _parse_missing_required(str(getattr(error, "message", "")))
        if missing:
            if path:
                return f"missing={path}.{missing}"
            return f"missing={missing}"
    if validator == "type":
        expected = getattr(error, "validator_value", None)
        expected_label = expected if isinstance(expected, str) else "unknown"
        if path:
            return f"path={path} expected={expected_label}"
        return f"path=<root> expected={expected_label}"

    if path:
        return f"path={path} validator={validator}"
    return f"validator={validator}"


def _parse_missing_required(message: str) -> str | None:
    match = _REQUIRED_PROP_RE.search(message)
    if not match:
        return None
    return match.group(1)


def _format_path(path: Sequence[Any]) -> str:
    if not path:
        return ""
    return ".".join(str(item) for item in path)


def _validate_minimal(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return "path=<root> expected=object"
    if "summary" not in payload:
        return "missing=summary"
    if "details" not in payload:
        return "missing=details"
    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        return "path=summary expected=object"
    if "markdown" not in summary:
        return "missing=summary.markdown"
    markdown = summary.get("markdown")
    if not isinstance(markdown, str):
        return "path=summary.markdown expected=string"
    details = payload.get("details")
    if not isinstance(details, Mapping):
        return "path=details expected=object"
    return None
