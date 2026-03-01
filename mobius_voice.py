"""
MOBIUS Voice — STT (Speech-to-Text) + TTS (Text-to-Speech)
STT: faster-whisper (lokalny, offline) + sounddevice
TTS: edge-tts (Microsoft, darmowy, dobra polszczyzna)
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

import logging

# TTS — edge-tts
TTS_AVAILABLE = False
try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    pass

# STT — faster-whisper + sounddevice (lokalny, offline)
STT_AVAILABLE = False
STT_BACKEND = "whisper"

try:
    import numpy as np
    import sounddevice as sd
    from faster_whisper import WhisperModel
    STT_AVAILABLE = True
except ImportError:
    pass

_whisper_model: Optional[Any] = None  # type: ignore[name-defined]


def _get_whisper_model() -> Optional[Any]:
    global _whisper_model
    if _whisper_model is None:
        try:
            logging.getLogger("faster_whisper").setLevel(logging.ERROR)
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception:
            return None
    return _whisper_model


def tts_speak(text: str, voice: str = "pl-PL-ZofiaNeural", blocking: bool = True) -> bool:
    """
    Odtwórz tekst przez edge-tts.
    voice: pl-PL-ZofiaNeural (żeński), pl-PL-MarekNeural (męski)
    """
    if not TTS_AVAILABLE or not text.strip():
        return False
    try:
        async def _run() -> str:
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                mp3_path = f.name
            await communicate.save(mp3_path)
            return mp3_path

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            mp3_path = loop.run_until_complete(_run())
            if blocking:
                subprocess.run(
                    ["cmd", "/c", "start", "/wait", "", mp3_path],
                    shell=True,
                    timeout=120,
                    capture_output=True,
                )
            else:
                subprocess.Popen(["cmd", "/c", "start", "", mp3_path], shell=True)
            Path(mp3_path).unlink(missing_ok=True)
            return True
        finally:
            loop.close()
    except Exception:
        return False


def stt_listen(timeout: float = 5, phrase_time_limit: float = 10) -> Optional[str]:
    """
    Nagraj z mikrofonu i transkrybuj lokalnie przez faster-whisper.
    Zatrzymuje się wcześniej gdy wykryje ciszę (RMS < 100) przez `timeout` sekund.
    """
    if not STT_AVAILABLE:
        return None
    model = _get_whisper_model()
    if model is None:
        return None
    try:
        sample_rate = 16000
        chunk_size = int(sample_rate * 0.1)  # 100ms chunks
        silence_threshold = 100
        silence_limit = int(timeout / 0.1)   # liczba cichych chunków = timeout

        frames: list[Any] = []
        silent_chunks = 0
        total_chunks = int(phrase_time_limit / 0.1)

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16") as stream:
            for _ in range(total_chunks):
                chunk, _ = stream.read(chunk_size)
                frames.append(chunk.copy())
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                if rms < silence_threshold:
                    silent_chunks += 1
                    if silent_chunks >= silence_limit:
                        break
                else:
                    silent_chunks = 0

        if not frames:
            return None
        audio_array = np.concatenate(frames, axis=0).flatten().astype(np.float32) / 32768.0
        segments, _ = model.transcribe(audio_array, language="pl", beam_size=5)
        text = " ".join(seg.text for seg in segments).strip()
        return text if text else None
    except Exception:
        return None
