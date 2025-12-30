from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping


class SerializationError(ValueError):
    """Raised when report serialization fails unexpectedly."""


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
