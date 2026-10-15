"""How long to wait for LAN MLX Whisper, and when local CPU Whisper may run.

A fixed 180s client timeout discarded a finished ~3 minute transcription, then
started local Whisper for about an hour. A read timeout means MLX had the job;
that path must stop instead of falling through to CPU.
"""

from __future__ import annotations

import subprocess

# Longer than this, local Whisper is not worth the wait.
CPU_FALLBACK_MAX_SECONDS = 30 * 60


class MlxTimedOut(TimeoutError):
    """MLX accepted the audio and did not answer before the read budget."""


class MlxUnreachable(ConnectionError):
    """Connect failed. This transcription never started on MLX."""


def read_timeout_seconds(duration_sec: int, floor: float = 180.0) -> float:
    """Read budget. Measured large-v3-turbo is about 16× realtime.

    Allow about 8× realtime plus 3 minutes. A 52 minute file (3091s) gets 566s;
    the run that was cut at 180s had already reached 100% in 177s.
    Unknown duration waits at least 10 minutes.
    """
    floor = float(floor) if floor and floor > 0 else 180.0
    if duration_sec <= 0:
        return max(floor, 600.0)
    return max(floor, duration_sec / 8.0 + 180.0)


def allow_cpu_fallback(exc: BaseException, duration_sec: int) -> bool:
    """CPU Whisper only for a short clip when MLX never started the job."""
    if isinstance(exc, MlxTimedOut):
        return False
    if duration_sec <= 0 or duration_sec > CPU_FALLBACK_MAX_SECONDS:
        return False
    return True


def probe_media_duration_seconds(path: str) -> int:
    if not path:
        return 0
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                path,
            ],
            text=True,
            timeout=30,
            stderr=subprocess.DEVNULL,
        )
        return max(0, int(float(out.strip() or "0")))
    except Exception:
        return 0
