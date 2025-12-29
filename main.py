import logging
import os

import functions_framework

from worker_llm_client.ops.config import ConfigurationError, WorkerConfig
from worker_llm_client.ops.logging import CloudLoggingEventLogger

logger = logging.getLogger(__name__)

try:
    CONFIG = WorkerConfig.from_env()
except ConfigurationError as exc:
    logger.error("Configuration error: %s", exc)
    raise

logging.basicConfig(level=getattr(logging, CONFIG.log_level, logging.INFO), format="%(message)s")

ENV_LABEL = os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "dev"
EVENT_LOGGER = CloudLoggingEventLogger(
    service="worker_llm_client",
    env=ENV_LABEL,
    component="worker_llm_client",
    logger=logger,
)


@functions_framework.cloud_event
def worker_llm_client(cloud_event):
    """Minimal stub entrypoint for deploy pipeline testing."""
    event_id = None
    event_type = None
    subject = None
    if hasattr(cloud_event, "get"):
        event_id = cloud_event.get("id")
        event_type = cloud_event.get("type")
        subject = cloud_event.get("subject")
    else:
        event_id = getattr(cloud_event, "id", None)
        event_type = getattr(cloud_event, "type", None)
        subject = getattr(cloud_event, "subject", None)

    EVENT_LOGGER.log(
        event="cloud_event_received",
        severity="INFO",
        eventId=event_id or "unknown",
        runId="unknown",
        stepId="unknown",
        eventType=event_type or "unknown",
        subject=subject or "unknown",
    )
    return "ok"
