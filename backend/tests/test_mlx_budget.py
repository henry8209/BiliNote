import unittest

from app.transcriber.mlx_budget import (
    CPU_FALLBACK_MAX_SECONDS,
    MlxTimedOut,
    MlxUnreachable,
    allow_cpu_fallback,
    read_timeout_seconds,
)


class TestMlxBudget(unittest.TestCase):
    def test_wait_is_measured_length_over_8(self):
        self.assertEqual(read_timeout_seconds(3091), 3091 / 8)
        self.assertEqual(read_timeout_seconds(0), 0)

    def test_a_working_mlx_never_starts_the_slow_path(self):
        self.assertFalse(allow_cpu_fallback(MlxTimedOut("cut"), 5 * 60))
        self.assertFalse(allow_cpu_fallback(MlxTimedOut("cut"), 52 * 60))
        self.assertFalse(allow_cpu_fallback(RuntimeError("HTTP 500"), 10 * 60))

    def test_slow_path_only_when_mlx_cannot_be_reached_and_clip_is_short(self):
        down = MlxUnreachable("down")
        self.assertTrue(allow_cpu_fallback(down, 10 * 60))
        self.assertFalse(allow_cpu_fallback(down, 0))
        self.assertFalse(allow_cpu_fallback(down, CPU_FALLBACK_MAX_SECONDS + 1))


if __name__ == "__main__":
    unittest.main()
