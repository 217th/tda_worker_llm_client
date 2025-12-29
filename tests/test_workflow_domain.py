import unittest

from worker_llm_client.workflow.domain import (
    FlowRun,
    FlowRunInvalid,
    InvalidStepInputs,
    LLMProfileInvalid,
    LLMReportInputs,
)
from worker_llm_client.workflow.policies import ReadyStepSelector


def _base_flow_run() -> dict:
    return {
        "runId": "run-1",
        "status": "RUNNING",
        "steps": {},
    }


def _llm_step(*, step_id: str, status: str, depends_on: list[str] | None = None) -> dict:
    return {
        "stepType": "LLM_REPORT",
        "status": status,
        "dependsOn": depends_on or [],
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
        },
        "outputs": {},
        "timeframe": "1M",
    }


def _artifact_step(*, step_id: str, status: str, gcs_uri: str | None) -> dict:
    outputs = {"gcs_uri": gcs_uri} if gcs_uri is not None else {}
    return {
        "stepType": "OHLCV_EXPORT",
        "status": status,
        "dependsOn": [],
        "inputs": {},
        "outputs": outputs,
    }


class FlowRunDomainTests(unittest.TestCase):
    def test_flow_run_invalid_step_id(self) -> None:
        flow_run = _base_flow_run()
        flow_run["steps"] = {"bad.step": {"stepType": "LLM_REPORT", "status": "READY", "dependsOn": []}}
        with self.assertRaises(FlowRunInvalid):
            FlowRun.from_raw(flow_run)

    def test_ready_selector_noop_when_run_not_running(self) -> None:
        flow_run = _base_flow_run()
        flow_run["status"] = "FAILED"
        flow = FlowRun.from_raw(flow_run)
        pick = ReadyStepSelector.pick(flow)
        self.assertIsNone(pick.step)
        self.assertEqual(pick.reason, "no_ready_step")

    def test_ready_selector_noop_when_no_ready_step(self) -> None:
        flow_run = _base_flow_run()
        flow_run["steps"] = {"llm-a": _llm_step(step_id="llm-a", status="PENDING")}
        flow = FlowRun.from_raw(flow_run)
        pick = ReadyStepSelector.pick(flow)
        self.assertIsNone(pick.step)
        self.assertEqual(pick.reason, "no_ready_step")

    def test_ready_selector_picks_lexicographic(self) -> None:
        flow_run = _base_flow_run()
        flow_run["steps"] = {
            "llm-b": _llm_step(step_id="llm-b", status="READY"),
            "llm-a": _llm_step(step_id="llm-a", status="READY"),
            "ohlcv": _artifact_step(step_id="ohlcv", status="SUCCEEDED", gcs_uri="gs://x/ohlcv.json"),
            "charts": _artifact_step(step_id="charts", status="SUCCEEDED", gcs_uri="gs://x/charts.json"),
        }
        flow = FlowRun.from_raw(flow_run)
        pick = ReadyStepSelector.pick(flow)
        self.assertIsNotNone(pick.step)
        self.assertEqual(pick.step.step.step_id, "llm-a")

    def test_ready_selector_dependency_blocked(self) -> None:
        flow_run = _base_flow_run()
        flow_run["steps"] = {
            "llm-a": _llm_step(step_id="llm-a", status="READY", depends_on=["dep-1"]),
            "dep-1": _artifact_step(step_id="dep-1", status="RUNNING", gcs_uri="gs://x/dep.json"),
            "ohlcv": _artifact_step(step_id="ohlcv", status="SUCCEEDED", gcs_uri="gs://x/ohlcv.json"),
            "charts": _artifact_step(step_id="charts", status="SUCCEEDED", gcs_uri="gs://x/charts.json"),
        }
        flow = FlowRun.from_raw(flow_run)
        pick = ReadyStepSelector.pick(flow)
        self.assertIsNone(pick.step)
        self.assertEqual(pick.reason, "dependency_not_succeeded")
        self.assertEqual(len(pick.blocked), 1)
        self.assertEqual(pick.blocked[0].step_id, "llm-a")
        self.assertEqual(pick.blocked[0].unmet[0].step_id, "dep-1")


class LLMReportInputsTests(unittest.TestCase):
    def _flow_run_for_inputs(self) -> FlowRun:
        flow_run = _base_flow_run()
        flow_run["steps"] = {
            "ohlcv": _artifact_step(step_id="ohlcv", status="SUCCEEDED", gcs_uri="gs://x/ohlcv.json"),
            "charts": _artifact_step(step_id="charts", status="SUCCEEDED", gcs_uri="gs://x/charts.json"),
            "prev": {
                "stepType": "LLM_REPORT",
                "status": "SUCCEEDED",
                "dependsOn": [],
                "inputs": {},
                "outputs": {"gcs_uri": "gs://x/prev.json"},
            },
        }
        return FlowRun.from_raw(flow_run)

    def test_inputs_happy_path(self) -> None:
        flow = self._flow_run_for_inputs()
        inputs = _llm_step(step_id="llm-a", status="READY")["inputs"]
        inputs["previousReportStepIds"] = ["prev"]
        parsed = LLMReportInputs.from_raw(inputs, flow_run=flow)
        self.assertEqual(parsed.prompt_id, "prompt-1")
        self.assertEqual(parsed.ohlcv_gcs_uri, "gs://x/ohlcv.json")
        self.assertEqual(parsed.charts_manifest_gcs_uri, "gs://x/charts.json")
        self.assertEqual(parsed.previous_report_gcs_uris, ("gs://x/prev.json",))

    def test_missing_prompt_id(self) -> None:
        flow = self._flow_run_for_inputs()
        inputs = _llm_step(step_id="llm-a", status="READY")["inputs"]
        del inputs["llm"]["promptId"]
        with self.assertRaises(InvalidStepInputs):
            LLMReportInputs.from_raw(inputs, flow_run=flow)

    def test_invalid_response_mime(self) -> None:
        flow = self._flow_run_for_inputs()
        inputs = _llm_step(step_id="llm-a", status="READY")["inputs"]
        inputs["llm"]["llmProfile"]["responseMimeType"] = "text/plain"
        with self.assertRaises(LLMProfileInvalid):
            LLMReportInputs.from_raw(inputs, flow_run=flow)

    def test_invalid_candidate_count(self) -> None:
        flow = self._flow_run_for_inputs()
        inputs = _llm_step(step_id="llm-a", status="READY")["inputs"]
        inputs["llm"]["llmProfile"]["candidateCount"] = 2
        with self.assertRaises(LLMProfileInvalid):
            LLMReportInputs.from_raw(inputs, flow_run=flow)

    def test_missing_schema_id(self) -> None:
        flow = self._flow_run_for_inputs()
        inputs = _llm_step(step_id="llm-a", status="READY")["inputs"]
        inputs["llm"]["llmProfile"]["structuredOutput"] = {}
        with self.assertRaises(LLMProfileInvalid):
            LLMReportInputs.from_raw(inputs, flow_run=flow)

    def test_missing_outputs_gcs_uri(self) -> None:
        flow_run = _base_flow_run()
        flow_run["steps"] = {
            "ohlcv": _artifact_step(step_id="ohlcv", status="SUCCEEDED", gcs_uri=None),
            "charts": _artifact_step(step_id="charts", status="SUCCEEDED", gcs_uri="gs://x/charts.json"),
        }
        flow = FlowRun.from_raw(flow_run)
        inputs = _llm_step(step_id="llm-a", status="READY")["inputs"]
        with self.assertRaises(InvalidStepInputs):
            LLMReportInputs.from_raw(inputs, flow_run=flow)

    def test_previous_report_must_be_llm_report(self) -> None:
        flow_run = _base_flow_run()
        flow_run["steps"] = {
            "ohlcv": _artifact_step(step_id="ohlcv", status="SUCCEEDED", gcs_uri="gs://x/ohlcv.json"),
            "charts": _artifact_step(step_id="charts", status="SUCCEEDED", gcs_uri="gs://x/charts.json"),
            "prev": _artifact_step(step_id="prev", status="SUCCEEDED", gcs_uri="gs://x/prev.json"),
        }
        flow = FlowRun.from_raw(flow_run)
        inputs = _llm_step(step_id="llm-a", status="READY")["inputs"]
        inputs["previousReportStepIds"] = ["prev"]
        with self.assertRaises(InvalidStepInputs):
            LLMReportInputs.from_raw(inputs, flow_run=flow)


if __name__ == "__main__":
    unittest.main()
