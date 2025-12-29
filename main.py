import logging

import functions_framework

logger = logging.getLogger(__name__)


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

    logger.info(
        "stub invocation: id=%s type=%s subject=%s",
        event_id,
        event_type,
        subject,
    )
    return "ok"
