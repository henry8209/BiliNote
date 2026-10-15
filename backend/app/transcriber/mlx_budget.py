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


def read_timeout_seconds(duration_sec: int) -> float:
    """Wait in proportion to the measured length. No fixed cutoff.

    MLX large-v3-turbo is about 16× realtime. Waiting at 8× (twice as long)
    is the whole budget: 3091s of audio → 386s. Unknown length → 0, caller stops.
    """
    if duration_sec <= 0:
        return 0.0
    return duration_sec / 8.0


def allow_cpu_fallback(exc: BaseException, duration_sec: int) -> bool:
    """The fast path did not deliver a transcript, so the slow path still runs."""
    del exc, duration_sec
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
