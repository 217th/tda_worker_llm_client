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
        self.assertEqual(config.invocation_timeout_seconds, 780)
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

    def test_artifacts_dry_run_parsed(self) -> None:
        env = {
            "ARTIFACTS_BUCKET": "test-bucket",
            "GEMINI_API_KEY": "sk_test_123",
            "ARTIFACTS_DRY_RUN": "true",
        }

        config = WorkerConfig.from_env(env)

        self.assertTrue(config.artifacts_dry_run)

        env["ARTIFACTS_DRY_RUN"] = "0"
        config = WorkerConfig.from_env(env)
        self.assertFalse(config.artifacts_dry_run)

    def test_artifacts_dry_run_invalid(self) -> None:
        env = {
            "ARTIFACTS_BUCKET": "test-bucket",
            "GEMINI_API_KEY": "sk_test_123",
            "ARTIFACTS_DRY_RUN": "maybe",
        }

        with self.assertRaises(ConfigurationError) as ctx:
            WorkerConfig.from_env(env)

        self.assertIn("ARTIFACTS_DRY_RUN", str(ctx.exception))

    def test_invocation_timeout_invalid(self) -> None:
        env = {
            "ARTIFACTS_BUCKET": "test-bucket",
            "GEMINI_API_KEY": "sk_test_123",
            "INVOCATION_TIMEOUT_SECONDS": "0",
        }

        with self.assertRaises(ConfigurationError) as ctx:
            WorkerConfig.from_env(env)

        self.assertIn("INVOCATION_TIMEOUT_SECONDS", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
