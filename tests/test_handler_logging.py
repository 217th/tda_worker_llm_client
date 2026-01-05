import unittest
from dataclasses import dataclass, field

from worker_llm_client.app.handler import FlowRunEventHandler, handle_cloud_event
from worker_llm_client.app.llm_client import ProviderResponse
from worker_llm_client.app.services import ClaimResult, FinalizeResult, FlowRunRecord, LLMPrompt, LLMSchema
from worker_llm_client.artifacts.domain import ArtifactPathPolicy, GcsUri
from worker_llm_client.artifacts.services import WriteResult
from worker_llm_client.reporting.services import ResolvedUserInput, UserInputPayload
from worker_llm_client.reporting.structured_output import StructuredOutputValidator
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
        self.claims: list[dict] = []
        self.finalized: list[dict] = []

    def get(self, run_id: str) -> FlowRunRecord | None:
        if self._flow_run is None:
            return None
        return FlowRunRecord(flow_run=self._flow_run, update_time="t1")

    def patch(self, run_id: str, patch: dict, *, precondition_update_time: str) -> None:
        return None

    def claim_step(self, run_id: str, step_id: str, started_at_rfc3339: str) -> ClaimResult:
        self.claims.append(
            {"run_id": run_id, "step_id": step_id, "started_at": started_at_rfc3339}
        )
        return ClaimResult(claimed=True, status="READY")

    def finalize_step(
        self,
        run_id: str,
        step_id: str,
        status: str,
        finished_at_rfc3339: str,
        *,
        outputs_gcs_uri: str | None = None,
        execution: dict | None = None,
        error: dict | None = None,
        allow_ready: bool = False,
    ) -> FinalizeResult:
        self.finalized.append(
            {
                "run_id": run_id,
                "step_id": step_id,
                "status": status,
                "finished_at": finished_at_rfc3339,
                "outputs_gcs_uri": outputs_gcs_uri,
                "execution": execution,
                "error": error,
            }
        )
        return FinalizeResult(updated=True, status="RUNNING")


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


class FakeArtifactStore:
    def read_bytes(self, uri: GcsUri) -> bytes:
        return b"{}"

    def exists(self, uri: GcsUri) -> bool:
        return True

    def write_bytes_create_only(self, uri: GcsUri, data: bytes, *, content_type: str) -> WriteResult:
        return WriteResult(uri=uri, created=True, reused=False)


class FakeLLMClient:
    def generate(self, *, system: str, user_parts, profile, llm_schema=None) -> ProviderResponse:
        return ProviderResponse(
            text='{"summary":{"markdown":"ok"},"details":{}}',
            finish_reason="STOP",
            usage={"promptTokens": 1, "candidatesTokens": 1},
            raw=None,
        )


class FakeUserInputAssembler:
    def resolve(self, *, flow_run: FlowRun, step, inputs, **_kwargs) -> ResolvedUserInput:
        ohlcv = type("JsonArtifact", (), {"uri": "gs://bucket/ohlcv.json", "bytes_len": 2})()
        charts_manifest = type(
            "JsonArtifact", (), {"uri": "gs://bucket/charts.json", "bytes_len": 2}
        )()
        return ResolvedUserInput(
            symbol="LINKUSDT",
            timeframe="1M",
            ohlcv=ohlcv,
            charts_manifest=charts_manifest,
            chart_images=(),
            previous_reports=(),
        )

    def assemble(self, *, base_user_prompt: str, resolved: ResolvedUserInput) -> UserInputPayload:
        return UserInputPayload(text="user prompt", chart_images=())


def _build_flow_run(schema_id: str | None = "llm_schema_1M_report_v1_0") -> FlowRun:
    llm_profile = {
        "modelName": "gemini-2.0-flash",
        "responseMimeType": "application/json",
        "candidateCount": 1,
        "structuredOutput": {"schemaId": schema_id} if schema_id is not None else {},
    }
    raw = {
        "runId": "run-1",
        "status": "RUNNING",
        "scope": {"symbol": "LINKUSDT"},
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
                "timeframe": "1M",
                "inputs": {
                    "llm": {"promptId": "llm_prompt_1M_report_v1_0", "llmProfile": llm_profile},
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
        prompt_id="llm_prompt_1M_report_v1_0",
        schema_version=1,
        system_instruction="sys",
        user_prompt="user",
    )


def _build_schema() -> LLMSchema:
    return LLMSchema(
        schema_id="llm_schema_1M_report_v1_0",
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
            artifact_store=FakeArtifactStore(),
            path_policy=ArtifactPathPolicy(bucket="bucket"),
            llm_client=FakeLLMClient(),
            user_input_assembler=FakeUserInputAssembler(),
            structured_output_validator=StructuredOutputValidator(),
            model_allowed=lambda _: True,
            invocation_timeout_seconds=780,
        )
        return result, logger.events

    def test_prompt_not_found(self) -> None:
        result, events = self._run(flow_run=_build_flow_run(), prompt=None, schema=None)
        self.assertEqual(result, "prompt_not_found")
        self.assertTrue(any(e["event"] == "prompt_fetch_started" for e in events))
        finished = [e for e in events if e["event"] == "prompt_fetch_finished"]
        self.assertEqual(len(finished), 1)

    def test_flow_run_event_handler_wrapper(self) -> None:
        logger = FakeEventLogger()
        handler = FlowRunEventHandler(
            flow_repo=FakeFlowRunRepo(_build_flow_run()),
            prompt_repo=FakePromptRepo(None),
            schema_repo=FakeSchemaRepo(None),
            event_logger=logger,
            flow_runs_collection="flow_runs",
            artifact_store=FakeArtifactStore(),
            path_policy=ArtifactPathPolicy(bucket="bucket"),
            llm_client=FakeLLMClient(),
            user_input_assembler=FakeUserInputAssembler(),
            structured_output_validator=StructuredOutputValidator(),
            model_allowed=lambda _: True,
            invocation_timeout_seconds=780,
        )
        result = handler.handle(
            {"id": "evt-1", "type": "google.cloud.firestore.document.v1.updated", "subject": "documents/flow_runs/run-1"}
        )
        self.assertEqual(result, "prompt_not_found")

    def test_invalid_subject_ignored(self) -> None:
        logger = FakeEventLogger()
        result = handle_cloud_event(
            {"id": "evt-1", "type": "google.cloud.firestore.document.v1.updated", "subject": "documents/other/run-1"},
            flow_repo=FakeFlowRunRepo(None),
            prompt_repo=FakePromptRepo(None),
            schema_repo=FakeSchemaRepo(None),
            event_logger=logger,
            flow_runs_collection="flow_runs",
            artifact_store=FakeArtifactStore(),
            path_policy=ArtifactPathPolicy(bucket="bucket"),
            llm_client=FakeLLMClient(),
            user_input_assembler=FakeUserInputAssembler(),
            structured_output_validator=StructuredOutputValidator(),
            model_allowed=lambda _: True,
            invocation_timeout_seconds=780,
        )
        self.assertEqual(result, "ignored")
        ignored = [e for e in logger.events if e["event"] == "cloud_event_ignored"]
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored[0]["reason"], "invalid_subject")

    def test_time_budget_guard(self) -> None:
        logger = FakeEventLogger()
        result = handle_cloud_event(
            {"id": "evt-1", "type": "google.cloud.firestore.document.v1.updated", "subject": "documents/flow_runs/run-1"},
            flow_repo=FakeFlowRunRepo(_build_flow_run()),
            prompt_repo=FakePromptRepo(_build_prompt()),
            schema_repo=FakeSchemaRepo(_build_schema()),
            event_logger=logger,
            flow_runs_collection="flow_runs",
            artifact_store=FakeArtifactStore(),
            path_policy=ArtifactPathPolicy(bucket="bucket"),
            llm_client=FakeLLMClient(),
            user_input_assembler=FakeUserInputAssembler(),
            structured_output_validator=StructuredOutputValidator(),
            model_allowed=lambda _: True,
            invocation_timeout_seconds=1,
            finalize_budget_seconds=120,
        )
        self.assertEqual(result, "failed")
        self.assertFalse(any(e["event"] == "llm_request_started" for e in logger.events))
        finished = [e for e in logger.events if e["event"] == "cloud_event_finished"][0]
        self.assertEqual(finished["error"]["code"], "TIME_BUDGET_EXCEEDED")

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
        self.assertEqual(result, "failed")
        finished = [e for e in events if e["event"] == "cloud_event_finished"][0]
        self.assertEqual(finished["error"]["code"], "LLM_PROFILE_INVALID")

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
