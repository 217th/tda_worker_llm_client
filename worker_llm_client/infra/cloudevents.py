"""CloudEvent parsing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CloudEventParser:
    """Parse Firestore CloudEvent subjects to extract runId."""

    flow_runs_collection: str

    def run_id_from_subject(self, subject: Any) -> str | None:
        if not isinstance(subject, str) or not subject.strip():
            return None
        parts = [part for part in subject.split("/") if part]
        for idx, part in enumerate(parts):
            if part == self.flow_runs_collection and idx + 1 < len(parts):
                run_id = parts[idx + 1].strip()
                return run_id or None
        return None
