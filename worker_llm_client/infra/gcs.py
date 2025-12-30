from __future__ import annotations

from dataclasses import dataclass

from worker_llm_client.artifacts.domain import GcsUri
from worker_llm_client.artifacts.services import (
    ArtifactReadFailed,
    ArtifactStore,
    ArtifactWriteFailed,
    WriteResult,
)

try:
    from google.api_core import exceptions as gax  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    gax = None


def _is_already_exists(exc: Exception) -> bool:
    if gax is not None:
        if isinstance(exc, (gax.PreconditionFailed, gax.Conflict, gax.AlreadyExists)):
            return True
    return exc.__class__.__name__ in ("PreconditionFailed", "Conflict", "AlreadyExists")


def _is_retryable(exc: Exception) -> bool:
    if gax is not None:
        retryable = (
            gax.ServiceUnavailable,
            gax.InternalServerError,
            gax.TooManyRequests,
            gax.DeadlineExceeded,
            gax.GatewayTimeout,
        )
        if isinstance(exc, retryable):
            return True
    return exc.__class__.__name__ in (
        "ServiceUnavailable",
        "InternalServerError",
        "TooManyRequests",
        "DeadlineExceeded",
        "GatewayTimeout",
    )


@dataclass(slots=True)
class GcsArtifactStore(ArtifactStore):
    client: object

    def read_bytes(self, uri: GcsUri) -> bytes:
        try:
            bucket = self.client.bucket(uri.bucket)
            blob = bucket.blob(uri.object_path)
            return blob.download_as_bytes()
        except Exception as exc:
            raise ArtifactReadFailed("GCS read failed", retryable=_is_retryable(exc)) from exc

    def exists(self, uri: GcsUri) -> bool:
        try:
            bucket = self.client.bucket(uri.bucket)
            blob = bucket.blob(uri.object_path)
            return bool(blob.exists())
        except Exception as exc:
            raise ArtifactReadFailed("GCS exists check failed", retryable=_is_retryable(exc)) from exc

    def write_bytes_create_only(self, uri: GcsUri, data: bytes, *, content_type: str) -> WriteResult:
        try:
            bucket = self.client.bucket(uri.bucket)
            blob = bucket.blob(uri.object_path)
            blob.upload_from_string(
                data,
                content_type=content_type,
                if_generation_match=0,
            )
            return WriteResult(uri=uri, created=True, reused=False)
        except Exception as exc:
            if _is_already_exists(exc):
                return WriteResult(uri=uri, created=False, reused=True)
            raise ArtifactWriteFailed("GCS write failed", retryable=_is_retryable(exc)) from exc
