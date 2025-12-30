from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from worker_llm_client.artifacts.domain import GcsUri


class ArtifactStoreError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class ArtifactReadFailed(ArtifactStoreError):
    pass


class ArtifactWriteFailed(ArtifactStoreError):
    pass


@dataclass(frozen=True, slots=True)
class WriteResult:
    uri: GcsUri
    created: bool
    reused: bool


class ArtifactStore(Protocol):
    def read_bytes(self, uri: GcsUri) -> bytes:
        ...

    def exists(self, uri: GcsUri) -> bool:
        ...

    def write_bytes_create_only(self, uri: GcsUri, data: bytes, *, content_type: str) -> WriteResult:
        ...
