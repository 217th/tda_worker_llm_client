import unittest

from worker_llm_client.ops.config import ConfigurationError, WorkerConfig


class WorkerConfigTests(unittest.TestCase):
    def test_single_key_happy_path(self) -> None:
        env = {
            "ARTIFACTS_BUCKET": "test-bucket",
            "GEMINI_API_KEY": "sk_test_123",
        }

        config = WorkerConfig.from_env(env)

        self.assertEqual(config.artifacts_bucket, "test-bucket")
        self.assertEqual(config.flow_runs_collection, "flow_runs")
        self.assertEqual(config.llm_prompts_collection, "llm_prompts")
        self.assertEqual(config.llm_models_collection, "llm_models")
        self.assertEqual(config.log_level, "INFO")
        self.assertTrue(config.is_model_allowed("gemini-2.0-flash"))

    def test_missing_api_key_is_rejected(self) -> None:
        env = {
            "ARTIFACTS_BUCKET": "test-bucket",
        }

        with self.assertRaises(ConfigurationError) as ctx:
            WorkerConfig.from_env(env)

        message = str(ctx.exception)
        self.assertIn("GEMINI_API_KEY", message)
        self.assertNotIn("sk_test", message)

    def test_empty_api_key_is_rejected(self) -> None:
        env = {
            "ARTIFACTS_BUCKET": "test-bucket",
            "GEMINI_API_KEY": "   ",
        }

        with self.assertRaises(ConfigurationError) as ctx:
            WorkerConfig.from_env(env)

        message = str(ctx.exception)
        self.assertIn("GEMINI_API_KEY", message)

    def test_error_messages_do_not_leak_api_key(self) -> None:
        env = {
            "ARTIFACTS_BUCKET": "",
            "GEMINI_API_KEY": "sk_test_secret",
            "LOG_LEVEL": "INFO",
        }

        with self.assertRaises(ConfigurationError) as ctx:
            WorkerConfig.from_env(env)

        message = str(ctx.exception)
        self.assertNotIn("sk_test_secret", message)


if __name__ == "__main__":
    unittest.main()
