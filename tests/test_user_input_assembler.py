import json
import unittest

from worker_llm_client.artifacts.domain import GcsUri
from worker_llm_client.artifacts.services import ArtifactStore
from worker_llm_client.reporting.services import UserInputAssembler
from worker_llm_client.workflow.domain import FlowRun, InvalidStepInputs, LLMReportStep


class FakeArtifactStore(ArtifactStore):
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads

    def read_bytes(self, uri: GcsUri) -> bytes:
        key = str(uri)
        if key not in self._payloads:
            raise InvalidStepInputs(f"missing artifact: {key}")
        return self._payloads[key]

    def exists(self, uri: GcsUri) -> bool:
        return str(uri) in self._payloads

    def write_bytes_create_only(self, uri: GcsUri, data: bytes, *, content_type: str):
        raise NotImplementedError


def _flow_run_base() -> dict:
    return {
        "runId": "run-1",
        "status": "RUNNING",
        "scope": {"symbol": "BTCUSDT"},
        "steps": {},
    }


def _llm_step_inputs() -> dict:
    return {
        "llm": {
            "promptId": "prompt-1",
            "llmProfile": {
                "responseMimeType": "application/json",
                "candidateCount": 1,
                "structuredOutput": {"schemaId": "llm_report_output_v1"},
            },
        },
        "ohlcvStepId": "ohlcv",
        "chartsManifestStepId": "charts",
        "previousReportStepIds": ["prev"],
    }


class UserInputAssemblerTests(unittest.TestCase):
    def _build_flow_run(self) -> FlowRun:
        flow_run = _flow_run_base()
        flow_run["steps"] = {
            "ohlcv": {
                "stepType": "OHLCV_EXPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "inputs": {},
                "outputs": {"gcs_uri": "gs://bucket/ohlcv.json"},
            },
            "charts": {
                "stepType": "CHART_EXPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "inputs": {},
                "outputs": {"gcs_uri": "gs://bucket/charts_manifest.json"},
            },
            "prev": {
                "stepType": "LLM_REPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "inputs": {},
                "outputs": {"gcs_uri": "gs://bucket/prev_report.json"},
            },
            "llm": {
                "stepType": "LLM_REPORT",
                "status": "READY",
                "dependsOn": [],
                "inputs": _llm_step_inputs(),
                "outputs": {},
                "timeframe": "1M",
            },
        }
        return FlowRun.from_raw(flow_run)

    def test_resolve_and_assemble(self) -> None:
        flow_run = self._build_flow_run()
        raw_step = flow_run.get_step("llm")
        self.assertIsNotNone(raw_step)
        step = LLMReportStep.from_flow_step(raw_step)
        inputs = step.parse_inputs(flow_run=flow_run)

        ohlcv = json.dumps({"rows": [1, 2, 3]})
        manifest = json.dumps(
            {
                "items": [
                    {
                        "gcsUri": "gs://bucket/chart1.png",
                        "description": "Price MA",
                    }
                ]
            }
        )
        prev_report = json.dumps({"summary": {"markdown": "ok"}, "details": {}})
        payloads = {
            "gs://bucket/ohlcv.json": ohlcv.encode("utf-8"),
            "gs://bucket/charts_manifest.json": manifest.encode("utf-8"),
            "gs://bucket/prev_report.json": prev_report.encode("utf-8"),
            "gs://bucket/chart1.png": b"png-data",
        }
        store = FakeArtifactStore(payloads)
        assembler = UserInputAssembler(artifact_store=store)
        resolved = assembler.resolve(flow_run=flow_run, step=step, inputs=inputs)
        payload = assembler.assemble(base_user_prompt="Analyze market.", resolved=resolved)

        self.assertIn("## UserInput", payload.text)
        self.assertIn("Symbol: BTCUSDT", payload.text)
        self.assertIn("Timeframe: 1M", payload.text)
        self.assertIn("ohlcv.json", payload.text)
        self.assertIn("charts_manifest.json", payload.text)
        self.assertIn("prev_report.json", payload.text)
        self.assertEqual(len(payload.chart_images), 1)

    def test_accepts_png_gcs_uri(self) -> None:
        flow_run = self._build_flow_run()
        raw_step = flow_run.get_step("llm")
        self.assertIsNotNone(raw_step)
        step = LLMReportStep.from_flow_step(raw_step)
        inputs = step.parse_inputs(flow_run=flow_run)

        manifest = json.dumps({"items": [{"png_gcs_uri": "gs://bucket/chart1.png"}]})
        payloads = {
            "gs://bucket/ohlcv.json": json.dumps({"rows": [1]}).encode("utf-8"),
            "gs://bucket/charts_manifest.json": manifest.encode("utf-8"),
            "gs://bucket/prev_report.json": json.dumps(
                {"summary": {"markdown": "ok"}, "details": {}}
            ).encode("utf-8"),
            "gs://bucket/chart1.png": b"png-data",
        }
        store = FakeArtifactStore(payloads)
        assembler = UserInputAssembler(artifact_store=store)
        resolved = assembler.resolve(flow_run=flow_run, step=step, inputs=inputs)

        self.assertEqual(len(resolved.chart_images), 1)
        self.assertEqual(resolved.chart_images[0].uri, "gs://bucket/chart1.png")

    def test_charts_manifest_outputs_manifest_gcs_uri(self) -> None:
        inputs = _llm_step_inputs()
        inputs["previousReportStepIds"] = []
        flow_run = _flow_run_base()
        flow_run["steps"] = {
            "ohlcv": {
                "stepType": "OHLCV_EXPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "inputs": {},
                "outputs": {"gcs_uri": "gs://bucket/ohlcv.json"},
            },
            "charts": {
                "stepType": "CHART_EXPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "inputs": {},
                "outputs": {"outputsManifestGcsUri": "gs://bucket/charts_manifest.json"},
            },
            "llm": {
                "stepType": "LLM_REPORT",
                "status": "READY",
                "dependsOn": [],
                "inputs": inputs,
                "outputs": {},
                "timeframe": "1M",
            },
        }
        flow = FlowRun.from_raw(flow_run)
        raw_step = flow.get_step("llm")
        self.assertIsNotNone(raw_step)
        step = LLMReportStep.from_flow_step(raw_step)
        inputs = step.parse_inputs(flow_run=flow)

        self.assertEqual(inputs.charts_manifest_gcs_uri, "gs://bucket/charts_manifest.json")

    def test_previous_report_external_gcs_uri(self) -> None:
        flow_run = _flow_run_base()
        flow_run["steps"] = {
            "ohlcv": {
                "stepType": "OHLCV_EXPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "inputs": {},
                "outputs": {"gcs_uri": "gs://bucket/ohlcv.json"},
            },
            "charts": {
                "stepType": "CHART_EXPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "inputs": {},
                "outputs": {"gcs_uri": "gs://bucket/charts_manifest.json"},
            },
            "llm": {
                "stepType": "LLM_REPORT",
                "status": "READY",
                "dependsOn": [],
                "inputs": {
                    "llm": {
                        "promptId": "prompt-1",
                        "llmProfile": {
                            "responseMimeType": "application/json",
                            "candidateCount": 1,
                            "structuredOutput": {"schemaId": "llm_report_output_v1"},
                        },
                    },
                    "ohlcvStepId": "ohlcv",
                    "chartsManifestStepId": "charts",
                    "previousReportStepIds": [],
                    "previousReports": [{"gcs_uri": "gs://bucket/external_report.json"}],
                },
                "outputs": {},
                "timeframe": "1M",
            },
        }
        flow = FlowRun.from_raw(flow_run)
        raw_step = flow.get_step("llm")
        self.assertIsNotNone(raw_step)
        step = LLMReportStep.from_flow_step(raw_step)
        inputs = step.parse_inputs(flow_run=flow)

        manifest = json.dumps({"items": [{"gcsUri": "gs://bucket/chart1.png"}]})
        payloads = {
            "gs://bucket/ohlcv.json": json.dumps({"rows": [1]}).encode("utf-8"),
            "gs://bucket/charts_manifest.json": manifest.encode("utf-8"),
            "gs://bucket/external_report.json": json.dumps(
                {"summary": {"markdown": "ok"}, "details": {}}
            ).encode("utf-8"),
            "gs://bucket/chart1.png": b"png-data",
        }
        store = FakeArtifactStore(payloads)
        assembler = UserInputAssembler(artifact_store=store)
        resolved = assembler.resolve(flow_run=flow, step=step, inputs=inputs)
        payload = assembler.assemble(base_user_prompt="Analyze market.", resolved=resolved)

        self.assertIn("external_report.json", payload.text)
        self.assertIn("external", payload.text)

    def test_chart_image_size_limit(self) -> None:
        flow_run = self._build_flow_run()
        raw_step = flow_run.get_step("llm")
        self.assertIsNotNone(raw_step)
        step = LLMReportStep.from_flow_step(raw_step)
        inputs = step.parse_inputs(flow_run=flow_run)

        manifest = json.dumps(
            {"items": [{"gcsUri": "gs://bucket/chart1.png", "description": "Price"}]}
        )
        payloads = {
            "gs://bucket/ohlcv.json": json.dumps({"rows": [1]}).encode("utf-8"),
            "gs://bucket/charts_manifest.json": manifest.encode("utf-8"),
            "gs://bucket/prev_report.json": json.dumps({"summary": {"markdown": "ok"}, "details": {}}).encode("utf-8"),
            "gs://bucket/chart1.png": b"x" * 300000,
        }
        store = FakeArtifactStore(payloads)
        assembler = UserInputAssembler(artifact_store=store)
        with self.assertRaises(InvalidStepInputs):
            assembler.resolve(flow_run=flow_run, step=step, inputs=inputs)

    def test_json_size_limit(self) -> None:
        flow_run = self._build_flow_run()
        raw_step = flow_run.get_step("llm")
        self.assertIsNotNone(raw_step)
        step = LLMReportStep.from_flow_step(raw_step)
        inputs = step.parse_inputs(flow_run=flow_run)

        huge = {"rows": ["x" * 2000] * 40}
        too_large = json.dumps(huge).encode("utf-8") + (b"x" * 70000)
        payloads = {
            "gs://bucket/ohlcv.json": too_large,
            "gs://bucket/charts_manifest.json": json.dumps({"items": []}).encode("utf-8"),
            "gs://bucket/prev_report.json": json.dumps({"summary": {"markdown": "ok"}, "details": {}}).encode("utf-8"),
        }
        store = FakeArtifactStore(payloads)
        assembler = UserInputAssembler(artifact_store=store)
        with self.assertRaises(InvalidStepInputs):
            assembler.resolve(flow_run=flow_run, step=step, inputs=inputs)


if __name__ == "__main__":
    unittest.main()
