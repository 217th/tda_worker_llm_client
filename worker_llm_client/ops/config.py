from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable, Mapping


ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


def _require_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value.strip():
        raise ConfigurationError(f"Missing required env var: {name}")
    return value


def _optional_env(env: Mapping[str, str], name: str, default: str | None = None) -> str | None:
    value = env.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _parse_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, "")
    if not raw.strip():
        return default
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid integer for {name}") from exc
    if parsed <= 0:
        raise ConfigurationError(f"Invalid integer for {name}")
    return parsed


def _parse_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigurationError(f"Invalid boolean for {name}")


def _parse_allowlist(raw: str) -> tuple[str, ...]:
    items = [item.strip() for item in raw.split(",")]
    items = [item for item in items if item]
    if not items:
        raise ConfigurationError("GEMINI_ALLOWED_MODELS must contain at least one model name")
    return tuple(dict.fromkeys(items))


@dataclass(frozen=True, slots=True, repr=False)
class GeminiApiKey:
    """Single Gemini API key for AI Studio (MVP)."""

    api_key: str

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ConfigurationError("GEMINI_API_KEY must be non-empty")

    def __repr__(self) -> str:  # pragma: no cover - defensive, but trivial
        return "GeminiApiKey(api_key=***redacted***)"


@dataclass(frozen=True, slots=True, repr=False)
class GeminiAuthConfig:
    """Gemini auth configuration (single-key)."""

    mode: str
    api_key: str

    def __post_init__(self) -> None:
        if self.mode != "ai_studio_api_key":
            raise ConfigurationError("Unsupported Gemini auth mode")
        if not self.api_key.strip():
            raise ConfigurationError("GEMINI_API_KEY must be non-empty")

    def __repr__(self) -> str:  # pragma: no cover - defensive, but trivial
        return "GeminiAuthConfig(mode='ai_studio_api_key', api_key=***redacted***)"


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    gcp_project: str | None
    gcp_region: str | None
    firestore_database: str
    flow_runs_collection: str
    llm_prompts_collection: str
    llm_models_collection: str
    artifacts_bucket: str
    artifacts_prefix: str | None
    artifacts_dry_run: bool
    gemini_api_key: GeminiApiKey
    gemini_auth: GeminiAuthConfig
    gemini_timeout_seconds: int
    finalize_budget_seconds: int
    invocation_timeout_seconds: int
    gemini_allowed_models: tuple[str, ...] | None
    log_level: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "WorkerConfig":
        env = env or os.environ

        gcp_project = _optional_env(env, "GCP_PROJECT")
        gcp_region = _optional_env(env, "GCP_REGION")
        firestore_database = _optional_env(env, "FIRESTORE_DATABASE", "(default)") or "(default)"
        flow_runs_collection = _optional_env(env, "FLOW_RUNS_COLLECTION", "flow_runs") or "flow_runs"
        llm_prompts_collection = _optional_env(env, "LLM_PROMPTS_COLLECTION", "llm_prompts") or "llm_prompts"
        llm_models_collection = _optional_env(env, "LLM_MODELS_COLLECTION", "llm_models") or "llm_models"
        artifacts_bucket = _require_env(env, "ARTIFACTS_BUCKET")
        artifacts_prefix = _optional_env(env, "ARTIFACTS_PREFIX")
        artifacts_dry_run = _parse_bool(env, "ARTIFACTS_DRY_RUN", False)

        if "/" in flow_runs_collection:
            raise ConfigurationError("FLOW_RUNS_COLLECTION must not contain '/'")
        if "/" in llm_prompts_collection:
            raise ConfigurationError("LLM_PROMPTS_COLLECTION must not contain '/'")
        if "/" in llm_models_collection:
            raise ConfigurationError("LLM_MODELS_COLLECTION must not contain '/'")

        gemini_key_raw = _require_env(env, "GEMINI_API_KEY")
        gemini_api_key = GeminiApiKey(api_key=gemini_key_raw)
        gemini_auth = GeminiAuthConfig(mode="ai_studio_api_key", api_key=gemini_key_raw)

        gemini_timeout_seconds = _parse_int(env, "GEMINI_TIMEOUT_SECONDS", 600)
        finalize_budget_seconds = _parse_int(env, "FINALIZE_BUDGET_SECONDS", 120)
        invocation_timeout_seconds = _parse_int(env, "INVOCATION_TIMEOUT_SECONDS", 780)

        allowed_models_raw = _optional_env(env, "GEMINI_ALLOWED_MODELS")
        gemini_allowed_models = (
            _parse_allowlist(allowed_models_raw) if allowed_models_raw is not None else None
        )

        log_level = (_optional_env(env, "LOG_LEVEL", "INFO") or "INFO").upper()
        if log_level not in ALLOWED_LOG_LEVELS:
            raise ConfigurationError("LOG_LEVEL must be one of DEBUG|INFO|WARNING|ERROR")

        return cls(
            gcp_project=gcp_project,
            gcp_region=gcp_region,
            firestore_database=firestore_database,
            flow_runs_collection=flow_runs_collection,
            llm_prompts_collection=llm_prompts_collection,
            llm_models_collection=llm_models_collection,
            artifacts_bucket=artifacts_bucket,
            artifacts_prefix=artifacts_prefix,
            artifacts_dry_run=artifacts_dry_run,
            gemini_api_key=gemini_api_key,
            gemini_auth=gemini_auth,
            gemini_timeout_seconds=gemini_timeout_seconds,
            finalize_budget_seconds=finalize_budget_seconds,
            invocation_timeout_seconds=invocation_timeout_seconds,
            gemini_allowed_models=gemini_allowed_models,
            log_level=log_level,
        )

    def is_model_allowed(self, model_name: str | None) -> bool:
        if model_name is None:
            return False
        if self.gemini_allowed_models is None:
            return True
        return model_name in self.gemini_allowed_models
