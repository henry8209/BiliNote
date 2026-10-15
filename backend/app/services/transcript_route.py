"""Choose the transcription route.

1. Platform subtitles, when the downloader has them. The caller does that first.
2. LAN MLX. Wait = measured duration / 8. A timeout means MLX is still the fast
   path, so the task stops.
3. Local CPU Whisper only when MLX cannot be reached and the clip is at most
   30 minutes. That path is about 20× slower, so it is not a fallback for a
   live MLX job or for a long video.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.transcriber.mlx_budget import (
    CPU_FALLBACK_MAX_SECONDS,
    MlxTimedOut,
    MlxUnreachable,
    allow_cpu_fallback,
    read_timeout_seconds,
)


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


def mlx_start(duration_sec: int) -> RouteDecision:
    if duration_sec <= 0:
        return RouteDecision(
            route=Route.STOP,
            message="未能從音檔讀到片長。已停止，不會改走慢路。",
        )
    wait = int(read_timeout_seconds(duration_sec))
    expect = mlx_expect_seconds(duration_sec)
    mins, secs = divmod(duration_sec, 60)
    return RouteDecision(
        route=Route.MLX,
        message=(
            f"音檔讀到 {mins} 分 {secs} 秒。走內網 MLX。"
            f"預計 {_clock(expect)}，等待上限 {_clock(wait)}（片長÷8）。"
            "逾時會停止，不會改走慢路。"
        ),
        eta_seconds=expect,
        pipeline="mlx_whisper_api",
        pipeline_label="內網 MLX Whisper",
    )


def after_mlx(exc: BaseException, duration_sec: int, threads: int = 3) -> RouteDecision:
    """What to do after an MLX attempt. Timeout never selects the slow path."""
    if allow_cpu_fallback(exc, duration_sec):
        eta = cpu_expect_seconds(duration_sec, threads)
        mins = max(1, duration_sec // 60)
        return RouteDecision(
            route=Route.CPU,
            message=(
                f"內網 MLX 連不上。這條片約 {mins} 分鐘，改用本機 Whisper。"
                f"預計約 {max(1, eta // 60)} 分鐘，大約比 MLX 慢二十倍。"
            ),
            eta_seconds=eta,
            pipeline="whisper_cpu",
            pipeline_label="本機 Whisper（MLX 連不上）",
        )
    if isinstance(exc, MlxTimedOut):
        message = "內網 MLX 仍在運作，等待上限到了。快捷方式沒有壞，已停止，不會改走慢路。"
    elif isinstance(exc, MlxUnreachable):
        eta = cpu_expect_seconds(duration_sec, threads) if duration_sec else 0
        extra = f"慢路大約要 {max(1, eta // 60)} 分鐘，" if eta else ""
        message = f"內網 MLX 連不上。片長超過 30 分鐘，{extra}已停止，不會自動開始慢路。"
    else:
        message = "內網 MLX 有回應，但這次結果沒有寫回。快捷方式沒有壞，已停止，不會改走慢路。"
    return RouteDecision(route=Route.STOP, message=message)


def without_mlx(duration_sec: int, threads: int = 3) -> RouteDecision:
    """MLX is not configured. Same gate as a machine that cannot be reached."""
    if 0 < duration_sec <= CPU_FALLBACK_MAX_SECONDS:
        eta = cpu_expect_seconds(duration_sec, threads)
        mins = max(1, duration_sec // 60)
        return RouteDecision(
            route=Route.CPU,
            message=(
                f"未設定內網 MLX。這條片約 {mins} 分鐘，改用本機 Whisper。"
                f"預計約 {max(1, eta // 60)} 分鐘。"
            ),
            eta_seconds=eta,
            pipeline="whisper_cpu",
            pipeline_label="本機 Whisper（未設定 MLX）",
        )
    if duration_sec > CPU_FALLBACK_MAX_SECONDS:
        eta = cpu_expect_seconds(duration_sec, threads)
        return RouteDecision(
            route=Route.STOP,
            message=(
                f"未設定內網 MLX。片長超過 30 分鐘，慢路大約要 {max(1, eta // 60)} 分鐘，"
                "已停止，不會自動開始。"
            ),
        )
    return RouteDecision(
        route=Route.STOP,
        message="未能從音檔讀到片長。已停止，不會改走慢路。",
    )
