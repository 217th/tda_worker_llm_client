import unittest
from dataclasses import dataclass, field

from worker_llm_client.app.handler import handle_cloud_event
from worker_llm_client.app.services import FlowRunRecord, LLMPrompt, LLMSchema
from worker_llm_client.workflow.domain import FlowRun


@dataclass
class FakeEventLogger:
    events: list[dict] = field(default_factory=list)

    def log(self, event: str, severity: str = "INFO", message: str | None = None, **fields) -> None:
        payload = {"event": event, "severity": severity, "message": message}
        payload.update(fields)
        self.events.append(payload)


class FakeFlowRunRepo:
    def __init__(self, flow_run: FlowRun | None) -> None:
        self._flow_run = flow_run

    def get(self, run_id: str) -> FlowRunRecord | None:
        if self._flow_run is None:
            return None
        return FlowRunRecord(flow_run=self._flow_run, update_time="t1")


class FakePromptRepo:
    def __init__(self, prompt: LLMPrompt | None) -> None:
        self._prompt = prompt

    def get(self, prompt_id: str) -> LLMPrompt | None:
        return self._prompt


class FakeSchemaRepo:
    def __init__(self, schema: LLMSchema | None) -> None:
        self._schema = schema

    def get(self, schema_id: str) -> LLMSchema | None:
        return self._schema


def _build_flow_run(schema_id: str | None = "llm_report_output_v1") -> FlowRun:
    llm_profile = {
        "modelName": "gemini-2.0-flash",
        "responseMimeType": "application/json",
        "candidateCount": 1,
        "structuredOutput": {"schemaId": schema_id} if schema_id is not None else {},
    }
    raw = {
        "runId": "run-1",
        "status": "RUNNING",
        "steps": {
            "ohlcv_1m_v1": {
                "stepType": "OHLCV_EXPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "outputs": {"gcs_uri": "gs://bucket/ohlcv.json"},
            },
            "charts_1m_v1": {
                "stepType": "CHART_EXPORT",
                "status": "SUCCEEDED",
                "dependsOn": ["ohlcv_1m_v1"],
                "outputs": {"gcs_uri": "gs://bucket/charts.json"},
            },
            "llm_report_1m_v1": {
                "stepType": "LLM_REPORT",
                "status": "READY",
                "dependsOn": ["ohlcv_1m_v1", "charts_1m_v1"],
                "inputs": {
                    "llm": {"promptId": "prompt_v1", "llmProfile": llm_profile},
                    "ohlcvStepId": "ohlcv_1m_v1",
                    "chartsManifestStepId": "charts_1m_v1",
                    "previousReportStepIds": [],
                },
                "outputs": {},
            },
        },
    }
    return FlowRun.from_raw(raw, run_id="run-1")


def _build_prompt() -> LLMPrompt:
    return LLMPrompt(
        prompt_id="prompt_v1",
        schema_version=1,
        system_instruction="sys",
        user_prompt="user",
    )


def _build_schema() -> LLMSchema:
    return LLMSchema(
        schema_id="llm_report_output_v1",
        kind="LLM_REPORT_OUTPUT",
        json_schema={
            "type": "object",
            "required": ["summary", "details"],
            "properties": {
                "summary": {
                    "type": "object",
                    "required": ["markdown"],
                    "properties": {"markdown": {"type": "string"}},
                },
                "details": {"type": "object"},
            },
        },
        sha256="a" * 64,
    )


class HandlerLoggingTests(unittest.TestCase):
    def _run(self, *, flow_run: FlowRun | None, prompt: LLMPrompt | None, schema: LLMSchema | None):
        logger = FakeEventLogger()
        result = handle_cloud_event(
            {"id": "evt-1", "type": "google.cloud.firestore.document.v1.updated", "subject": "documents/flow_runs/run-1"},
            flow_repo=FakeFlowRunRepo(flow_run),
            prompt_repo=FakePromptRepo(prompt),
            schema_repo=FakeSchemaRepo(schema),
            event_logger=logger,
            flow_runs_collection="flow_runs",
        )
        return result, logger.events

    def test_prompt_not_found(self) -> None:
        result, events = self._run(flow_run=_build_flow_run(), prompt=None, schema=None)
        self.assertEqual(result, "prompt_not_found")
        self.assertTrue(any(e["event"] == "prompt_fetch_started" for e in events))
        finished = [e for e in events if e["event"] == "prompt_fetch_finished"]
        self.assertEqual(len(finished), 1)
        self.assertFalse(finished[0].get("ok"))
        self.assertEqual(finished[0]["error"]["code"], "PROMPT_NOT_FOUND")

    def test_schema_missing(self) -> None:
        result, events = self._run(flow_run=_build_flow_run(), prompt=_build_prompt(), schema=None)
        self.assertEqual(result, "schema_invalid")
        self.assertTrue(any(e["event"] == "structured_output_schema_invalid" for e in events))
        invalid = [e for e in events if e["event"] == "structured_output_schema_invalid"][0]
        self.assertEqual(invalid["error"]["code"], "LLM_PROFILE_INVALID")

    def test_schema_id_missing(self) -> None:
        result, events = self._run(
            flow_run=_build_flow_run(schema_id=None),
            prompt=_build_prompt(),
            schema=_build_schema(),
        )
        self.assertEqual(result, "schema_invalid")
        invalid = [e for e in events if e["event"] == "structured_output_schema_invalid"][0]
        self.assertEqual(invalid["error"]["code"], "LLM_PROFILE_INVALID")

    def test_ok_path(self) -> None:
        result, events = self._run(
            flow_run=_build_flow_run(),
            prompt=_build_prompt(),
            schema=_build_schema(),
        )
        self.assertEqual(result, "ok")
        finished = [e for e in events if e["event"] == "prompt_fetch_finished"][0]
        self.assertTrue(finished.get("ok"))
        self.assertFalse(any(e["event"] == "structured_output_schema_invalid" for e in events))


if __name__ == "__main__":
    unittest.main()
