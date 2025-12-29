import json
import logging
import unittest

from worker_llm_client.ops.logging import CloudLoggingEventLogger, LogPayloadError


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


class EventLoggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = ListHandler()
        self.logger = logging.getLogger("test_logger")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = [self.handler]

        self.event_logger = CloudLoggingEventLogger(
            service="worker_llm_client",
            env="test",
            component="worker_llm_client",
            logger=self.logger,
        )

    def test_cloud_event_received_payload(self) -> None:
        self.event_logger.log(
            event="cloud_event_received",
            severity="INFO",
            eventId="evt-1",
            runId="run-1",
            stepId="step-1",
            eventType="google.cloud.firestore.document.v1.updated",
            subject="documents/flow_runs/run-1",
        )

        self.assertEqual(len(self.handler.records), 1)
        payload = json.loads(self.handler.records[0])
        self.assertEqual(payload["event"], "cloud_event_received")
        self.assertEqual(payload["eventId"], "evt-1")
        self.assertEqual(payload["runId"], "run-1")
        self.assertEqual(payload["stepId"], "step-1")
        self.assertEqual(payload["severity"], "INFO")

    def test_missing_required_fields_rejected(self) -> None:
        with self.assertRaises(LogPayloadError):
            self.event_logger.log(
                event="cloud_event_received",
                severity="INFO",
                eventId="evt-1",
                runId="",
            )

    def test_forbidden_key_rejected(self) -> None:
        with self.assertRaises(LogPayloadError):
            self.event_logger.log(
                event="cloud_event_received",
                severity="INFO",
                eventId="evt-1",
                runId="run-1",
                stepId="step-1",
                apiKey="secret",
            )

    def test_prompt_payload_rejected(self) -> None:
        with self.assertRaises(LogPayloadError):
            self.event_logger.log(
                event="cloud_event_received",
                severity="INFO",
                eventId="evt-1",
                runId="run-1",
                stepId="step-1",
                systemInstruction="do not log this",
            )

    def test_string_size_limit_rejected(self) -> None:
        with self.assertRaises(LogPayloadError):
            self.event_logger.log(
                event="cloud_event_received",
                severity="INFO",
                eventId="evt-1",
                runId="run-1",
                stepId="step-1",
                note="x" * 5000,
            )

    def test_array_size_limit_rejected(self) -> None:
        with self.assertRaises(LogPayloadError):
            self.event_logger.log(
                event="cloud_event_received",
                severity="INFO",
                eventId="evt-1",
                runId="run-1",
                stepId="step-1",
                items=list(range(300)),
            )


if __name__ == "__main__":
    unittest.main()
