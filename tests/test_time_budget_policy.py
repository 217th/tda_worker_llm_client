import unittest

from worker_llm_client.ops.time_budget import TimeBudgetPolicy


class TimeBudgetPolicyTests(unittest.TestCase):
    def test_remaining_seconds_floor(self) -> None:
        policy = TimeBudgetPolicy(
            invocation_started_at=100.0,
            invocation_timeout_seconds=10,
            finalize_budget_seconds=3,
        )
        self.assertAlmostEqual(policy.remaining_seconds(105.0), 5.0)
        self.assertEqual(policy.remaining_seconds(120.0), 0.0)

    def test_can_start_llm_call(self) -> None:
        policy = TimeBudgetPolicy(
            invocation_started_at=0.0,
            invocation_timeout_seconds=10,
            finalize_budget_seconds=4,
        )
        self.assertTrue(policy.can_start_llm_call(5.0))
        self.assertFalse(policy.can_start_llm_call(7.0))


if __name__ == "__main__":
    unittest.main()
