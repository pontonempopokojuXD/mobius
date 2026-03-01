"""MOBIUS Wake Word — always-on "Mobius" detector using faster-whisper."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

WAKEWORD_AVAILABLE = False

try:
    import numpy as np
    import sounddevice as sd
    from faster_whisper import WhisperModel
    WAKEWORD_AVAILABLE = True
except ImportError:
    pass

log = logging.getLogger("mobius_wakeword")
logging.getLogger("faster_whisper").setLevel(logging.ERROR)

_tiny_model: Optional[object] = None


def _get_tiny_model() -> Optional[object]:
    global _tiny_model
    if _tiny_model is None:
        try:
            _tiny_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        except Exception as e:
            log.error("Nie można załadować modelu tiny: %s", e)
    return _tiny_model


class WakeWordListener:
    def __init__(self, config: dict) -> None:
        self._config = config
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="WakeWordListener")
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        model = _get_tiny_model()
        if model is None:
            log.error("Wake word: brak modelu tiny, kończę wątek")
            return

        sample_rate = 16000
        chunk_samples = sample_rate * 2
        vad_threshold: float = self._config.get("wakeword_vad_threshold", 0.01)

        try:
            from mobius_events import get_bus, WAKE_WORD_DETECTED
            _bus = get_bus()
        except ImportError:
            _bus = None

        while self.running:
            try:
                audio_chunk = sd.rec(
                    chunk_samples,
                    samplerate=sample_rate,
                    channels=1,
                    dtype="int16",
                    blocking=True,
                )
                audio_flat = audio_chunk.flatten().astype("float32") / 32768.0

                rms = float(np.sqrt(np.mean(audio_flat ** 2)))
                if rms < vad_threshold:
                    continue

                segments, _ = model.transcribe(audio_flat, language="pl", beam_size=1)
                text = " ".join(seg.text for seg in segments).lower()
                if "mobius" in text or "möbius" in text:
                    log.info("Wake word wykryty: %s", text)
                    if _bus is not None:
                        _bus.publish(WAKE_WORD_DETECTED, {})
                    time.sleep(0.5)
                else:
                    time.sleep(0.05)
            except Exception as e:
                log.warning("Wake word pętla: %s", e)
                time.sleep(1)
