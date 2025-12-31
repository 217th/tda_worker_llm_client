import unittest

from worker_llm_client.infra.cloudevents import CloudEventParser


class CloudEventParserTests(unittest.TestCase):
    def test_parses_run_id(self) -> None:
        parser = CloudEventParser(flow_runs_collection="flow_runs")
        self.assertEqual(
            parser.run_id_from_subject("documents/flow_runs/run-1"),
            "run-1",
        )

    def test_invalid_subject_returns_none(self) -> None:
        parser = CloudEventParser(flow_runs_collection="flow_runs")
        self.assertIsNone(parser.run_id_from_subject(""))
        self.assertIsNone(parser.run_id_from_subject(None))
        self.assertIsNone(parser.run_id_from_subject("documents/other/run-1"))


if __name__ == "__main__":
    unittest.main()
