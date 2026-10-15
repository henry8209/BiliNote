import unittest

from app.transcriber.mlx_budget import (
    CPU_FALLBACK_MAX_SECONDS,
    MlxTimedOut,
    MlxUnreachable,
    allow_cpu_fallback,
    read_timeout_seconds,
)


class TestMlxBudget(unittest.TestCase):
    def test_long_file_waits_past_the_old_180s_cap(self):
        # 51 min 31 sec. The live job finished frames in 177s and was cut at 180s.
        timeout = read_timeout_seconds(3091, floor=180)
        self.assertGreater(timeout, 180)
        self.assertGreaterEqual(timeout, 3091 / 8 + 180)

    def test_unknown_duration_is_not_left_at_180s(self):
        self.assertGreaterEqual(read_timeout_seconds(0, floor=180), 600)

    def test_configured_floor_can_raise_the_budget(self):
        self.assertEqual(read_timeout_seconds(60, floor=900), 900)
        self.assertAlmostEqual(read_timeout_seconds(60, floor=180), 187.5)

    def test_read_timeout_never_starts_cpu_whisper(self):
        self.assertFalse(allow_cpu_fallback(MlxTimedOut("cut"), 5 * 60))
        self.assertFalse(allow_cpu_fallback(MlxTimedOut("cut"), 52 * 60))

    def test_long_or_unknown_audio_never_starts_cpu_whisper(self):
        down = MlxUnreachable("down")
        self.assertFalse(allow_cpu_fallback(down, 0))
        self.assertFalse(allow_cpu_fallback(down, CPU_FALLBACK_MAX_SECONDS + 1))
        self.assertFalse(allow_cpu_fallback(RuntimeError("HTTP 500"), 52 * 60))

    def test_short_clip_may_use_cpu_when_mlx_did_not_start(self):
        self.assertTrue(allow_cpu_fallback(MlxUnreachable("down"), 10 * 60))
        self.assertTrue(allow_cpu_fallback(RuntimeError("HTTP 500"), 10 * 60))


if __name__ == "__main__":
    unittest.main()
