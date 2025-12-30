import unittest

from worker_llm_client.infra.firestore import FirestorePromptRepository, FirestoreSchemaRepository


class FakeSnapshot:
    def __init__(self, data: dict | None, *, exists: bool = True) -> None:
        self._data = data
        self.exists = exists

    def to_dict(self) -> dict | None:
        return self._data


class FakeDocRef:
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self._snapshots = snapshots

    def get(self) -> FakeSnapshot:
        if self._snapshots:
            return self._snapshots.pop(0)
        return FakeSnapshot({}, exists=True)


class FakeClient:
    def __init__(self, doc_ref: FakeDocRef) -> None:
        self._doc_ref = doc_ref

    def collection(self, name: str) -> "FakeClient":
        return self

    def document(self, doc_id: str) -> FakeDocRef:
        return self._doc_ref


class PromptRepositoryTests(unittest.TestCase):
    def test_get_prompt_success(self) -> None:
        snapshot = FakeSnapshot(
            {"schemaVersion": 1, "systemInstruction": "sys", "userPrompt": "user"}
        )
        repo = FirestorePromptRepository(FakeClient(FakeDocRef([snapshot])))
        prompt = repo.get("prompt_v1")
        self.assertIsNotNone(prompt)
        assert prompt is not None
        self.assertEqual(prompt.prompt_id, "prompt_v1")
        self.assertEqual(prompt.schema_version, 1)

    def test_get_prompt_missing(self) -> None:
        snapshot = FakeSnapshot(None, exists=False)
        repo = FirestorePromptRepository(FakeClient(FakeDocRef([snapshot])))
        self.assertIsNone(repo.get("prompt_v1"))

    def test_get_prompt_invalid_doc(self) -> None:
        snapshot = FakeSnapshot({"schemaVersion": 2, "systemInstruction": "", "userPrompt": ""})
        repo = FirestorePromptRepository(FakeClient(FakeDocRef([snapshot])))
        self.assertIsNone(repo.get("prompt_v1"))

    def test_get_prompt_invalid_id(self) -> None:
        repo = FirestorePromptRepository(FakeClient(FakeDocRef([])))
        with self.assertRaises(ValueError):
            repo.get("bad.id")


class SchemaRepositoryTests(unittest.TestCase):
    def _valid_schema_doc(self, *, schema_id: str = "llm_report_output_v1") -> dict:
        return {
            "schemaId": schema_id,
            "kind": "LLM_REPORT_OUTPUT",
            "jsonSchema": {
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
            "sha256": "a" * 64,
        }

    def test_get_schema_success(self) -> None:
        snapshot = FakeSnapshot(self._valid_schema_doc())
        repo = FirestoreSchemaRepository(FakeClient(FakeDocRef([snapshot])))
        schema = repo.get("llm_report_output_v1")
        self.assertIsNotNone(schema)
        assert schema is not None
        self.assertEqual(schema.schema_id, "llm_report_output_v1")

    def test_get_schema_missing(self) -> None:
        snapshot = FakeSnapshot(None, exists=False)
        repo = FirestoreSchemaRepository(FakeClient(FakeDocRef([snapshot])))
        self.assertIsNone(repo.get("llm_report_output_v1"))

    def test_get_schema_invalid_id(self) -> None:
        repo = FirestoreSchemaRepository(FakeClient(FakeDocRef([])))
        with self.assertRaises(ValueError):
            repo.get("bad_schema")

    def test_get_schema_mismatch_id(self) -> None:
        snapshot = FakeSnapshot(self._valid_schema_doc(schema_id="llm_report_output_v2"))
        repo = FirestoreSchemaRepository(FakeClient(FakeDocRef([snapshot])))
        self.assertIsNone(repo.get("llm_report_output_v1"))

    def test_get_schema_invalid_invariants(self) -> None:
        doc = self._valid_schema_doc()
        doc["jsonSchema"]["required"] = ["summary"]
        snapshot = FakeSnapshot(doc)
        repo = FirestoreSchemaRepository(FakeClient(FakeDocRef([snapshot])))
        self.assertIsNone(repo.get("llm_report_output_v1"))

    def test_get_schema_invalid_sha256(self) -> None:
        doc = self._valid_schema_doc()
        doc["sha256"] = "not-hex"
        snapshot = FakeSnapshot(doc)
        repo = FirestoreSchemaRepository(FakeClient(FakeDocRef([snapshot])))
        self.assertIsNone(repo.get("llm_report_output_v1"))


if __name__ == "__main__":
    unittest.main()
