from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from typing import Any


MAX_STRING_LENGTH = 4096
MAX_ARRAY_LENGTH = 200

VALID_SEVERITIES = {"DEBUG", "INFO", "WARNING", "ERROR"}
_SEVERITY_TO_LEVEL = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

FORBIDDEN_KEYS = {
    "apikey",
    "api_key",
    "token",
    "secret",
    "authorization",
    "credentials",
    "systeminstruction",
    "userprompt",
    "prompttext",
    "candidatetext",
    "rawoutput",
    "outputtext",
}


class LogPayloadError(ValueError):
    """Raised when a log payload violates safety gates."""


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_required(payload: dict[str, Any], required: tuple[str, ...]) -> None:
    for key in required:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise LogPayloadError(f"Missing or invalid required field: {key}")

    severity = payload.get("severity")
    if severity not in VALID_SEVERITIES:
        raise LogPayloadError("Invalid severity")


def _check_forbidden_keys(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_str = str(key)
            if key_str.lower() in FORBIDDEN_KEYS:
                raise LogPayloadError(f"Forbidden key in payload: {path}{key_str}")
            _check_forbidden_keys(item, path=f"{path}{key_str}.")
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            _check_forbidden_keys(item, path=f"{path}{idx}.")


def _check_sizes(value: Any) -> None:
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise LogPayloadError("String field exceeds size limit")
        return
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ARRAY_LENGTH:
            raise LogPayloadError("Array field exceeds size limit")
        for item in value:
            _check_sizes(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            _check_sizes(item)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return f"<non-serializable:{type(value).__name__}>"


class EventLogger:
    """Abstract event logger interface."""

    def log(self, event: str, severity: str = "INFO", message: str | None = None, **fields: Any) -> None:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class CloudLoggingEventLogger(EventLogger):
    service: str
    env: str
    component: str
    logger: logging.Logger | None = None

    def __post_init__(self) -> None:
        if not self.service.strip() or not self.env.strip() or not self.component.strip():
            raise LogPayloadError("service/env/component must be non-empty strings")

    def log(self, event: str, severity: str = "INFO", message: str | None = None, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "service": self.service,
            "env": self.env,
            "component": self.component,
            "event": event,
            "severity": severity,
            "message": message or event,
            "time": _now_rfc3339(),
        }
        payload.update(fields)

        payload.setdefault("eventId", "unknown")
        payload.setdefault("runId", "unknown")

        _validate_required(
            payload,
            ("service", "env", "component", "event", "severity", "message", "time", "eventId", "runId"),
        )
        _check_forbidden_keys(payload)
        _check_sizes(payload)

        safe_payload = _json_safe(payload)
        serialized = json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"))

        target_logger = self.logger or logging.getLogger(__name__)
        target_logger.log(_SEVERITY_TO_LEVEL[severity], serialized)
