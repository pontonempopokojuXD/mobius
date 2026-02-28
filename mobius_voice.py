"""
MOBIUS Voice — STT (Speech-to-Text) + TTS (Text-to-Speech)
Wymaga: edge-tts (TTS), SpeechRecognition + PyAudio (STT).
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# TTS — edge-tts (Microsoft, darmowy, dobra polszczyzna)
TTS_AVAILABLE = False
try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    pass

# STT — SpeechRecognition
STT_AVAILABLE = False
try:
    import speech_recognition as sr
    STT_AVAILABLE = True
except ImportError:
    pass


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
    Nagraj z mikrofonu i zwróć transkrypcję.
    Wymaga: SpeechRecognition, PyAudio.
    Używa Google Speech Recognition (online) — fallback na inną metodę jeśli brak.
    """
    if not STT_AVAILABLE:
        return None
    try:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.3)
            audio = r.record(source, duration=phrase_time_limit, phrase_time_limit=phrase_time_limit)
        try:
            return r.recognize_google(audio, language="pl-PL")
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            # Fallback: try Whisper API if available, or return None
            return None
    except Exception:
        return None
