import unittest

from app.services.transcript_route import Route, after_mlx, mlx_start, without_mlx
from app.transcriber.mlx_budget import MlxTimedOut, MlxUnreachable


class TestTranscriptRoute(unittest.TestCase):
    def test_mlx_wait_is_twice_the_expected_time(self):
        decision = mlx_start(3091)
        self.assertEqual(decision.route, Route.MLX)
        self.assertIn("51 分 31 秒", decision.message)
        self.assertIn("6 分 26 秒", decision.message)
        self.assertIn("改走本機 Whisper", decision.message)
        self.assertEqual(decision.eta_seconds, 3091 // 16)

    def test_unknown_length_still_tries_mlx(self):
        self.assertEqual(mlx_start(0).route, Route.MLX)

    def test_timeout_takes_the_remaining_path(self):
        for duration in (5 * 60, 52 * 60):
            decision = after_mlx(MlxTimedOut("cut"), duration)
            self.assertEqual(decision.route, Route.CPU)
            self.assertIn("改走本機 Whisper", decision.message)

    def test_mlx_http_error_takes_the_remaining_path(self):
        decision = after_mlx(RuntimeError("HTTP 500"), 10 * 60)
        self.assertEqual(decision.route, Route.CPU)

    def test_unreachable_takes_the_remaining_path_for_any_length(self):
        short = after_mlx(MlxUnreachable("down"), 10 * 60)
        long = after_mlx(MlxUnreachable("down"), 52 * 60)
        self.assertEqual(short.route, Route.CPU)
        self.assertEqual(long.route, Route.CPU)
        self.assertGreater(long.eta_seconds, 60 * 60)

    def test_unconfigured_mlx_still_runs(self):
        self.assertEqual(without_mlx(10 * 60).route, Route.CPU)
        self.assertEqual(without_mlx(52 * 60).route, Route.CPU)
        self.assertEqual(without_mlx(0).route, Route.CPU)


if __name__ == "__main__":
    unittest.main()
