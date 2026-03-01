"""
MOBIUS Voice — STT (Speech-to-Text) + TTS (Text-to-Speech)
STT: faster-whisper (lokalny, offline) + sounddevice
TTS: edge-tts z barge-in (przerwanie przez stop_tts())
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import threading
import time
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

_whisper_model: Optional[Any] = None
_tts_stop_event = threading.Event()


def _get_whisper_model() -> Optional[Any]:
    global _whisper_model
    if _whisper_model is None:
        try:
            logging.getLogger("faster_whisper").setLevel(logging.ERROR)
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception:
            return None
    return _whisper_model


def stop_tts() -> None:
    """Przerwij aktualnie odtwarzany TTS."""
    _tts_stop_event.set()


def tts_speak(text: str, voice: str = "pl-PL-ZofiaNeural", blocking: bool = True) -> bool:
    if not TTS_AVAILABLE or not text.strip():
        return False
    _tts_stop_event.clear()
    try:
        async def _synthesize() -> str:
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                mp3_path = f.name
            await communicate.save(mp3_path)
            return mp3_path

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            mp3_path = loop.run_until_complete(_synthesize())
            uri = "file:///" + mp3_path.replace("\\", "/")
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-c",
                 f"Add-Type -AssemblyName presentationCore; "
                 f"$mp = New-Object System.Windows.Media.MediaPlayer; "
                 f"$mp.Open([uri]'{uri}'); $mp.Play(); "
                 f"Start-Sleep -Milliseconds ($mp.NaturalDuration.TimeSpan.TotalMilliseconds + 500); "
                 f"$mp.Close()"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if blocking:
                while proc.poll() is None:
                    if _tts_stop_event.is_set():
                        proc.terminate()
                        break
                    time.sleep(0.5)
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
        chunk_size = int(sample_rate * 0.1)
        silence_threshold = 100
        silence_limit = int(timeout / 0.1)

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
