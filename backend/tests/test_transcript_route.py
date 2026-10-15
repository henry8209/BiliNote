import unittest

from app.services.transcript_route import Route, after_mlx, mlx_start, without_mlx
from app.transcriber.mlx_budget import MlxTimedOut, MlxUnreachable


class TestTranscriptRoute(unittest.TestCase):
    def test_mlx_wait_follows_measured_length(self):
        decision = mlx_start(3091)
        self.assertEqual(decision.route, Route.MLX)
        self.assertIn("51 分 31 秒", decision.message)
        self.assertIn("6 分 26 秒", decision.message)
        self.assertIn("不會改走慢路", decision.message)
        self.assertEqual(decision.eta_seconds, 3091 // 16)

    def test_unknown_length_stops(self):
        self.assertEqual(mlx_start(0).route, Route.STOP)

    def test_timeout_never_takes_the_slow_path(self):
        for duration in (5 * 60, 52 * 60):
            decision = after_mlx(MlxTimedOut("cut"), duration)
            self.assertEqual(decision.route, Route.STOP)
            self.assertIn("不會改走慢路", decision.message)

    def test_mlx_http_error_never_takes_the_slow_path(self):
        decision = after_mlx(RuntimeError("HTTP 500"), 10 * 60)
        self.assertEqual(decision.route, Route.STOP)

    def test_short_clip_uses_cpu_only_when_mlx_is_down(self):
        decision = after_mlx(MlxUnreachable("down"), 10 * 60)
        self.assertEqual(decision.route, Route.CPU)
        self.assertIn("連不上", decision.message)

    def test_long_clip_stops_when_mlx_is_down(self):
        decision = after_mlx(MlxUnreachable("down"), 52 * 60)
        self.assertEqual(decision.route, Route.STOP)
        self.assertIn("不會自動開始慢路", decision.message)

    def test_unconfigured_mlx_follows_the_same_gate(self):
        self.assertEqual(without_mlx(10 * 60).route, Route.CPU)
        self.assertEqual(without_mlx(52 * 60).route, Route.STOP)


if __name__ == "__main__":
    unittest.main()
