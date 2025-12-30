import json
import unittest

from worker_llm_client.app.services import LLMSchema
from worker_llm_client.reporting.structured_output import StructuredOutputValidator
from worker_llm_client.reporting.domain import StructuredOutputInvalid


def _schema() -> LLMSchema:
    raw = {
        "schemaId": "llm_report_output_v1",
        "kind": "LLM_REPORT_OUTPUT",
        "jsonSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "details"],
            "properties": {
                "summary": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["markdown"],
                    "properties": {"markdown": {"type": "string"}},
                },
                "details": {"type": "object", "additionalProperties": True},
            },
        },
        "sha256": "0" * 64,
    }
    return LLMSchema.from_raw(raw, schema_id="llm_report_output_v1")


class StructuredOutputValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = StructuredOutputValidator()
        self.schema = _schema()

    def test_valid_payload(self) -> None:
        payload = json.dumps({"summary": {"markdown": "ok"}, "details": {}})
        result = self.validator.validate(text=payload, llm_schema=self.schema)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["summary"]["markdown"], "ok")

    def test_missing_required(self) -> None:
        payload = json.dumps({"summary": {}, "details": {}})
        result = self.validator.validate(text=payload, llm_schema=self.schema)
        self.assertIsInstance(result, StructuredOutputInvalid)
        self.assertEqual(result.kind, "schema_validation")
        self.assertIn("missing=summary.markdown", result.to_error_message())

    def test_wrong_type(self) -> None:
        payload = json.dumps({"summary": {"markdown": 123}, "details": {}})
        result = self.validator.validate(text=payload, llm_schema=self.schema)
        self.assertIsInstance(result, StructuredOutputInvalid)
        self.assertIn("path=summary.markdown", result.to_error_message())

    def test_truncated_json(self) -> None:
        payload = "{\"summary\":{\"markdown\":\"ok\"},\"details\":"
        result = self.validator.validate(
            text=payload, llm_schema=self.schema, finish_reason="MAX_TOKENS"
        )
        self.assertIsInstance(result, StructuredOutputInvalid)
        self.assertEqual(result.kind, "json_parse")
        self.assertIn("finishReason=MAX_TOKENS", result.to_error_message())

    def test_missing_text(self) -> None:
        result = self.validator.validate(text=None, llm_schema=self.schema)
        self.assertIsInstance(result, StructuredOutputInvalid)
        self.assertEqual(result.kind, "missing_text")


if __name__ == "__main__":
    unittest.main()
