import unittest

from app.transcriber.mlx_budget import (
    MlxTimedOut,
    MlxUnreachable,
    allow_cpu_fallback,
    read_timeout_seconds,
)


class TestMlxBudget(unittest.TestCase):
    def test_wait_is_measured_length_over_8(self):
        self.assertEqual(read_timeout_seconds(3091), 3091 / 8)
        self.assertEqual(read_timeout_seconds(0), 0)

    def test_a_missed_fast_path_still_runs_the_slow_path(self):
        self.assertTrue(allow_cpu_fallback(MlxTimedOut("cut"), 52 * 60))
        self.assertTrue(allow_cpu_fallback(MlxUnreachable("down"), 52 * 60))
        self.assertTrue(allow_cpu_fallback(RuntimeError("HTTP 500"), 10 * 60))
        self.assertTrue(allow_cpu_fallback(MlxUnreachable("down"), 0))


if __name__ == "__main__":
    unittest.main()
