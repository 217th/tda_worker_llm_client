import logging
import os

import functions_framework

from worker_llm_client.app.handler import handle_cloud_event
from worker_llm_client.infra.gemini import GeminiClientAdapter
from worker_llm_client.artifacts.domain import ArtifactPathPolicy
from worker_llm_client.infra.firestore import (
    FirestoreFlowRunRepository,
    FirestorePromptRepository,
    FirestoreSchemaRepository,
)
from worker_llm_client.infra.gcs import GcsArtifactStore
from worker_llm_client.ops.config import ConfigurationError, WorkerConfig
from worker_llm_client.ops.logging import CloudLoggingEventLogger, configure_logging
from worker_llm_client.reporting.services import UserInputAssembler
from worker_llm_client.reporting.structured_output import StructuredOutputValidator

configure_logging()
logger = logging.getLogger(__name__)
try:
    CONFIG = WorkerConfig.from_env()
except ConfigurationError as exc:
    logger.error("Configuration error: %s", exc)
    raise

configure_logging(level=CONFIG.log_level)

try:
    from google.cloud import firestore  # type: ignore
except Exception as exc:  # pragma: no cover - runtime guard
    logger.error("Firestore client unavailable: %s", exc)
    raise

FIRESTORE_CLIENT = firestore.Client(
    project=CONFIG.gcp_project,
    database=CONFIG.firestore_database,
)
FLOW_RUN_REPO = FirestoreFlowRunRepository(
    FIRESTORE_CLIENT, flow_runs_collection=CONFIG.flow_runs_collection
)
PROMPT_REPO = FirestorePromptRepository(
    FIRESTORE_CLIENT, prompts_collection=CONFIG.llm_prompts_collection
)
SCHEMA_REPO = FirestoreSchemaRepository(FIRESTORE_CLIENT)

try:
    from google.cloud import storage  # type: ignore
except Exception as exc:  # pragma: no cover - runtime guard
    logger.error("GCS client unavailable: %s", exc)
    raise

STORAGE_CLIENT = storage.Client(project=CONFIG.gcp_project)
ARTIFACT_STORE = GcsArtifactStore(STORAGE_CLIENT)
ARTIFACT_PATH_POLICY = ArtifactPathPolicy.from_config(CONFIG)
USER_INPUT_ASSEMBLER = UserInputAssembler(artifact_store=ARTIFACT_STORE)
STRUCTURED_OUTPUT_VALIDATOR = StructuredOutputValidator()
LLM_CLIENT = GeminiClientAdapter(
    api_key=CONFIG.gemini_auth.api_key,
    timeout_seconds=CONFIG.gemini_timeout_seconds,
)

ENV_LABEL = os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "dev"
EVENT_LOGGER = CloudLoggingEventLogger(
    service="worker_llm_client",
    env=ENV_LABEL,
    component="worker_llm_client",
    logger=logging.getLogger(),
)


@functions_framework.cloud_event
def worker_llm_client(cloud_event):
    """CloudEvent handler for LLM report execution (MVP)."""
    return handle_cloud_event(
        cloud_event,
        flow_repo=FLOW_RUN_REPO,
        prompt_repo=PROMPT_REPO,
        schema_repo=SCHEMA_REPO,
        event_logger=EVENT_LOGGER,
        flow_runs_collection=CONFIG.flow_runs_collection,
        artifact_store=ARTIFACT_STORE,
        path_policy=ARTIFACT_PATH_POLICY,
        artifacts_dry_run=CONFIG.artifacts_dry_run,
        llm_client=LLM_CLIENT,
        user_input_assembler=USER_INPUT_ASSEMBLER,
        structured_output_validator=STRUCTURED_OUTPUT_VALIDATOR,
        model_allowed=CONFIG.is_model_allowed,
        finalize_budget_seconds=CONFIG.finalize_budget_seconds,
    )
