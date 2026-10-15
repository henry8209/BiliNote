"""Choose the transcription route.

1. Platform subtitles, when the downloader has them. The caller does that first.
2. LAN MLX. Wait = measured duration / 8, twice the expected time.
3. If MLX does not hand back a transcript, run local CPU Whisper. Stopping
   would mean no note. The slow path is about 20× slower, so the status says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.transcriber.mlx_budget import MlxTimedOut, MlxUnreachable, read_timeout_seconds


class Route(str, Enum):
    MLX = "mlx"
    CPU = "cpu"
    STOP = "stop"


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    message: str
    eta_seconds: int = 0
    pipeline: str = ""
    pipeline_label: str = ""


def _clock(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60} 分 {seconds % 60} 秒"


def mlx_expect_seconds(duration_sec: int) -> int:
    """Measured large-v3-turbo is about 16× realtime."""
    if duration_sec <= 0:
        return 0
    return max(1, duration_sec // 16)


def cpu_expect_seconds(duration_sec: int, threads: int = 3) -> int:
    if duration_sec <= 0:
        return 0
    factor = 1.7 if threads <= 2 else (1.45 if threads == 3 else 1.35)
    return max(1, int(duration_sec * factor))


def _cpu(reason: str, duration_sec: int, threads: int, label: str) -> RouteDecision:
    eta = cpu_expect_seconds(duration_sec, threads) if duration_sec > 0 else 0
    eta_text = f"預計約 {max(1, eta // 60)} 分鐘。" if eta else "片長未知，完成時間視音檔而定。"
    return RouteDecision(
        route=Route.CPU,
        message=f"{reason}{eta_text}這條路大約比 MLX 慢二十倍。",
        eta_seconds=eta,
        pipeline="whisper_cpu",
        pipeline_label=label,
    )


def mlx_start(duration_sec: int) -> RouteDecision:
    if duration_sec <= 0:
        return RouteDecision(
            route=Route.MLX,
            message="未能從音檔讀到片長，仍先走內網 MLX。交唔到結果就改走本機 Whisper。",
            eta_seconds=0,
            pipeline="mlx_whisper_api",
            pipeline_label="內網 MLX Whisper",
        )
    wait = int(read_timeout_seconds(duration_sec))
    expect = mlx_expect_seconds(duration_sec)
    mins, secs = divmod(duration_sec, 60)
    return RouteDecision(
        route=Route.MLX,
        message=(
            f"音檔讀到 {mins} 分 {secs} 秒。走內網 MLX。"
            f"預計 {_clock(expect)}，等待上限 {_clock(wait)}（預計時間再加一倍）。"
            "交唔到結果就改走本機 Whisper。"
        ),
        eta_seconds=expect,
        pipeline="mlx_whisper_api",
        pipeline_label="內網 MLX Whisper",
    )


def after_mlx(exc: BaseException, duration_sec: int, threads: int = 3) -> RouteDecision:
    """Fast path did not deliver a transcript. Run the remaining path."""
    if isinstance(exc, MlxTimedOut):
        reason = "內網 MLX 在等待上限內沒有交到結果，改走本機 Whisper。"
        label = "本機 Whisper（MLX 未交結果）"
    elif isinstance(exc, MlxUnreachable):
        reason = "內網 MLX 連不上，改走本機 Whisper。"
        label = "本機 Whisper（MLX 連不上）"
    else:
        reason = "內網 MLX 沒有交到結果，改走本機 Whisper。"
        label = "本機 Whisper（MLX 未交結果）"
    return _cpu(reason, duration_sec, threads, label)


def without_mlx(duration_sec: int, threads: int = 3) -> RouteDecision:
    """MLX is not configured. The remaining path still runs."""
    return _cpu(
        "未設定內網 MLX，改走本機 Whisper。",
        duration_sec,
        threads,
        "本機 Whisper（未設定 MLX）",
    )
