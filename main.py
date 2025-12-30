import logging
import os

import functions_framework

from worker_llm_client.app.handler import handle_cloud_event
from worker_llm_client.infra.firestore import FirestoreFlowRunRepository, FirestorePromptRepository
from worker_llm_client.ops.config import ConfigurationError, WorkerConfig
from worker_llm_client.ops.logging import CloudLoggingEventLogger, configure_logging

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

ENV_LABEL = os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "dev"
EVENT_LOGGER = CloudLoggingEventLogger(
    service="worker_llm_client",
    env=ENV_LABEL,
    component="worker_llm_client",
    logger=logging.getLogger(),
)


@functions_framework.cloud_event
def worker_llm_client(cloud_event):
    """CloudEvent handler for prompt/schema preflight (MVP)."""
    return handle_cloud_event(
        cloud_event,
        flow_repo=FLOW_RUN_REPO,
        prompt_repo=PROMPT_REPO,
        event_logger=EVENT_LOGGER,
        flow_runs_collection=CONFIG.flow_runs_collection,
    )
