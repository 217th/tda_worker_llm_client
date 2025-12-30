from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from worker_llm_client.ops.config import WorkerConfig


class InvalidGcsUri(ValueError):
    """Raised when a GCS URI is invalid."""


class InvalidIdentifier(ValueError):
    """Raised when a path identifier (runId/timeframe/stepId) is invalid."""


_TIMEFRAME_TOKEN_RE = re.compile(r"^[0-9]+[A-Za-z]+$")


@dataclass(frozen=True, slots=True)
class GcsUri:
    bucket: str
    object_path: str

    def __post_init__(self) -> None:
        if not self.bucket or not self.bucket.strip():
            raise InvalidGcsUri("bucket must be non-empty")
        if not self.object_path or not self.object_path.strip():
            raise InvalidGcsUri("object_path must be non-empty")
        if self.object_path.startswith("/"):
            raise InvalidGcsUri("object_path must not start with '/'")
        if "?" in self.object_path or "#" in self.object_path:
            raise InvalidGcsUri("object_path must not include query/fragment")

    def __str__(self) -> str:
        return f"gs://{self.bucket}/{self.object_path}"

    @classmethod
    def parse(cls, value: str) -> "GcsUri":
        if not isinstance(value, str) or not value.strip():
            raise InvalidGcsUri("GCS URI must be a non-empty string")
        value = value.strip()
        if not value.startswith("gs://"):
            raise InvalidGcsUri("GCS URI must start with gs://")
        path = value[len("gs://") :]
        if not path or "/" not in path:
            raise InvalidGcsUri("GCS URI must include bucket and object path")
        bucket, object_path = path.split("/", 1)
        return cls(bucket=bucket, object_path=object_path)


@dataclass(frozen=True, slots=True)
class ArtifactPathPolicy:
    bucket: str
    prefix: str | None = None

    def __post_init__(self) -> None:
        if not self.bucket or not self.bucket.strip():
            raise InvalidIdentifier("bucket must be non-empty")

    @classmethod
    def from_config(cls, config: WorkerConfig) -> "ArtifactPathPolicy":
        return cls(bucket=config.artifacts_bucket, prefix=config.artifacts_prefix)

    def report_uri(self, run_id: str, timeframe: str, step_id: str) -> GcsUri:
        run_id = _require_identifier(run_id, label="runId")
        timeframe = _require_identifier(timeframe, label="timeframe")
        step_id = _require_identifier(step_id, label="stepId")
        _validate_timeframe_in_step_id(timeframe, step_id)

        prefix = _normalize_prefix(self.prefix)
        filename = f"{step_id}.json"
        segments = [segment for segment in (prefix, run_id, timeframe, filename) if segment]
        object_path = "/".join(segments)
        return GcsUri(bucket=self.bucket, object_path=object_path)


def _normalize_prefix(prefix: str | None) -> str | None:
    if prefix is None:
        return None
    cleaned = prefix.strip().strip("/")
    return cleaned or None


def _require_identifier(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidIdentifier(f"{label} must be a non-empty string")
    if "/" in value:
        raise InvalidIdentifier(f"{label} must not contain '/'")
    return value.strip()


def _validate_timeframe_in_step_id(timeframe: str, step_id: str) -> None:
    tokens = [token for token in step_id.split("_") if token]
    timeframe_tokens = [token for token in tokens if _TIMEFRAME_TOKEN_RE.fullmatch(token)]
    if not timeframe_tokens:
        return
    for token in timeframe_tokens:
        if token.lower() != timeframe.lower():
            raise InvalidIdentifier("timeframe does not match timeframe token in stepId")
