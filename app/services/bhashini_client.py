"""
Phase J — Bhashini (IndiaAI) speech interfaces, offline-first.

Speech-to-text for worker availability already works fully offline via
`app.services.voice` (rule-based, bilingual Hinglish/Hindi/English) and TTS is
left to the browser. This module gives those same capabilities a uniform
interface with an *optional*, env-gated Bhashini fallback for cases where the
offline parser fails to produce a confident result.

Configuration (all optional; if unset, the offline path is used exclusively):
    BHASHINI_STT_ENDPOINT  — e.g. https://bhashini.gov.in/...
    BHASHINI_TTS_ENDPOINT  — e.g. https://bhashini.gov.in/...
    BHASHINI_API_KEY       — bearer token for the above
    BHASHINI_LANGUAGE_ID   — "hi" (default) or "en"

Design:
    - No network calls are made unless the endpoints/keys are configured.
    - `stt()` returns a transcript string; `parse()` runs it through voice.
    - Failures in the remote path are caught and the offline result is returned,
      so the feature degrades gracefully on device.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from app.services.voice import parse_availability

log = logging.getLogger("sahakarsetu.services.bhashini")


@dataclass
class SpeechConfig:
    stt_endpoint: str | None = os.environ.get("BHASHINI_STT_ENDPOINT")
    tts_endpoint: str | None = os.environ.get("BHASHINI_TTS_ENDPOINT")
    api_key: str | None = os.environ.get("BHASHINI_API_KEY")
    language_id: str = os.environ.get("BHASHINI_LANGUAGE_ID", "hi")

    @property
    def remote_enabled(self) -> bool:
        return bool(self.stt_endpoint and self.api_key)


class BhashiniClient:
    """Offline-first STT/TTS facade with an optional Bhashini fallback."""

    def __init__(self, config: SpeechConfig | None = None) -> None:
        self.config = config or SpeechConfig()

    # ── speech to text ───────────────────────────────────────────────────

    def _stt_remote(self, audio_bytes: bytes) -> str:
        import requests  # local import: only needed when remote is enabled
        headers = {"Authorization": f"Bearer {self.config.api_key}",
                   "Content-Type": "application/octet-stream"}
        resp = requests.post(self.config.stt_endpoint, data=audio_bytes,
                             headers=headers, timeout=8)
        resp.raise_for_status()
        return _extract_transcript(resp.json())

    def stt(self, audio_bytes: bytes, offline_transcript: str = "") -> str:
        """Best-effort STT: try Bhashini first if configured, otherwise use the
        offline transcript (e.g. from the browser Web Speech API), then fall
        back to offline. Always returns a string."""
        if self.config.remote_enabled:
            try:
                return self._stt_remote(audio_bytes)
            except Exception as exc:  # network / auth / format
                log.warning("Bhashini STT failed (%s); falling back to offline transcript.", exc)
        return offline_transcript

    # ── text to speech (TTS) ───────────────────────────────────────────────

    def tts(self, text: str) -> bytes | None:
        """Return audio bytes via Bhashini if configured; otherwise ``None``
        (the PWA reads text aloud itself via the Web Speech API)."""
        if not (self.config.tts_endpoint and self.config.api_key):
            return None
        import requests
        headers = {"Authorization": f"Bearer {self.config.api_key}",
                   "Content-Type": "application/json"}
        payload = {"text": text, "language": self.config.language_id, "task": "tts"}
        try:
            resp = requests.post(self.config.tts_endpoint, json=payload, headers=headers, timeout=8)
            resp.raise_for_status()
            return _extract_audio(resp.json())
        except Exception as exc:
            log.warning("Bhashini TTS failed: %s", exc)
            return None

    # ── end-to-end availability parse ──────────────────────────────────────

    def parse(self, audio_bytes: bytes, offline_transcript: str = "", reference_date=None) -> dict:
        transcription = self.stt(audio_bytes, offline_transcript)
        result = parse_availability(transcription, reference_date)
        payload: dict = {"transcript": transcription}
        if hasattr(result, "model_dump"):
            payload.update(result.model_dump())
        else:
            payload.update(dict(result))
        return payload


def _extract_transcript(payload: dict) -> str:
    if isinstance(payload, dict):
        if "transcript" in payload:
            return payload["transcript"]
        if "output" in payload and isinstance(payload["output"], list):
            return " ".join(str(o) for o in payload["output"])
        if "data" in payload:
            return str(payload["data"])
    return ""


def _extract_audio(payload: dict) -> bytes:
    if isinstance(payload, dict):
        for key in ("audio", "audioContent", "data", "base64", "audio_base64"):
            if key in payload and payload[key]:
                import base64
                val = payload[key]
                if isinstance(val, str):
                    return base64.b64decode(val)
                if isinstance(val, (bytes, bytearray)):
                    return bytes(val)
    return b""


client = BhashiniClient()
