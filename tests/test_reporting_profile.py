import unittest

from worker_llm_client.reporting.domain import LLMProfile, StructuredOutputSpec
from worker_llm_client.workflow.domain import LLMProfileInvalid


class LLMProfileTests(unittest.TestCase):
    def test_profile_happy_path(self) -> None:
        raw = {
            "modelName": "gemini-2.5-flash-lite",
            "temperature": 0.2,
            "candidateCount": 1,
            "responseMimeType": "application/json",
            "structuredOutput": {"schemaId": "llm_schema_1M_report_v1_0", "kind": "LLM_REPORT_OUTPUT"},
        }
        profile = LLMProfile.from_raw(raw)
        profile.validate_for_mvp()
        provider = profile.to_provider_request()
        self.assertEqual(provider["model"], "gemini-2.5-flash-lite")
        self.assertEqual(provider["config"]["responseMimeType"], "application/json")

    def test_profile_missing_schema(self) -> None:
        raw = {
            "modelName": "gemini-2.5-flash-lite",
            "candidateCount": 1,
            "responseMimeType": "application/json",
        }
        profile = LLMProfile.from_raw(raw)
        with self.assertRaises(LLMProfileInvalid):
            profile.validate_for_mvp()

    def test_profile_invalid_schema_id(self) -> None:
        raw = {
            "modelName": "gemini-2.5-flash-lite",
            "candidateCount": 1,
            "responseMimeType": "application/json",
            "structuredOutput": {"schemaId": "bad", "kind": "LLM_REPORT_OUTPUT"},
        }
        profile = LLMProfile.from_raw(raw)
        with self.assertRaises(LLMProfileInvalid):
            profile.validate_for_mvp()


class StructuredOutputSpecTests(unittest.TestCase):
    def test_schema_version(self) -> None:
        spec = StructuredOutputSpec(schema_id="llm_schema_1M_report_v12_3")
        self.assertEqual(spec.schema_version(), 12)

    def test_invalid_sha(self) -> None:
        with self.assertRaises(LLMProfileInvalid):
            StructuredOutputSpec(schema_id="llm_schema_1M_report_v1_0", schema_sha256="bad")

    def test_from_raw(self) -> None:
        raw = {"schemaId": "llm_schema_1M_report_v1_0", "kind": "LLM_REPORT_OUTPUT"}
        spec = StructuredOutputSpec.from_raw(raw)
        payload = spec.to_dict()
        self.assertEqual(payload["schemaId"], "llm_schema_1M_report_v1_0")


if __name__ == "__main__":
    unittest.main()
