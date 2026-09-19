"""OpenAI-compatible MLX Whisper HTTP client (LAN)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests

from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.transcriber.base import Transcriber
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MlxApiTranscriber(Transcriber):
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        model: Optional[str] = None,
    ):
        raw = (base_url or os.getenv("MLX_WHISPER_API_URL") or "").strip().rstrip("/")
        self.base_url = raw
        self.endpoint = f"{self.base_url}/v1/audio/transcriptions" if raw else ""
        try:
            self.timeout = float(timeout or os.getenv("MLX_WHISPER_TIMEOUT", "180"))
        except ValueError:
            self.timeout = 180.0
        self.model = model or os.getenv("MLX_WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")

    def available(self) -> bool:
        return bool(self.endpoint)

    def transcript(self, file_path: str) -> TranscriptResult:
        if not self.endpoint:
            raise RuntimeError("MLX_WHISPER_API_URL 未配置")
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        logger.info(f"MLX API 转写: {self.endpoint} file={path.name} timeout={self.timeout}s")
        with path.open("rb") as f:
            files = {"file": (path.name, f, "application/octet-stream")}
            data = {
                "model": self.model,
                "response_format": "verbose_json",
            }
            resp = requests.post(
                self.endpoint,
                files=files,
                data=data,
                timeout=self.timeout,
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"MLX API HTTP {resp.status_code}: {resp.text[:300]}")

        payload = resp.json()
        text = (payload.get("text") or "").strip()
        if not text:
            raise RuntimeError("MLX API 返回空文本")

        language = payload.get("language") or "zh"
        raw_segments = payload.get("segments") or []
        segments: list[TranscriptSegment] = []
        if raw_segments:
            for seg in raw_segments:
                t = (seg.get("text") or "").strip()
                if not t:
                    continue
                start = float(seg.get("start") or 0)
                end = float(seg.get("end") or start)
                segments.append(TranscriptSegment(start=start, end=end, text=t))
        if not segments:
            segments = [TranscriptSegment(start=0.0, end=0.0, text=text)]

        return TranscriptResult(
            language=language,
            full_text=text,
            segments=segments,
            raw={"source": "mlx_whisper_api", "endpoint": self.endpoint},
        )
