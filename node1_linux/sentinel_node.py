"""
MOBIUS – Sentinel Node (Node 1 / Ubuntu Server 24.04 LTS)
Master process: VAD → Whisper STT → 3-tier router → local | Ollama | gRPC→Titan

Routing tiers:
  1. local   — bash/system commands     → subprocess
  2. ollama  — short/fast queries       → Ollama API localhost:11434 (1B model)
  3. titan   — complex/long LLM tasks   → gRPC → Node 2 RTX 5060 Ti

Start:
  python sentinel_node.py [--titan-host IP] [--mode text|mic]
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator, Optional

import grpc
import ollama as ollama_lib

# ── Generated gRPC stubs (run: python -m grpc_tools.protoc ...) ──────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "generated"))
import mobius_pb2
import mobius_pb2_grpc

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SENTINEL] %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("sentinel")

SENTINEL_VERSION = "2.0.0"

MOBIUS_SYSTEM_PROMPT = (
    "You are MOBIUS, a distributed AI assistant running across two nodes: "
    "a Linux master (Node 1) and a Windows GPU worker (Node 2, RTX 5060 Ti). "
    "Rules you must follow strictly:\n"
    "1. Always refer to yourself as MOBIUS.\n"
    "2. Be concise and precise.\n"
    "3. NEVER invent facts, names, dates, or data you are not certain about. "
    "If you do not know something, say exactly: 'I don't know.' — do not guess.\n"
    "4. If a question is ambiguous, ask for clarification instead of assuming.\n"
    "5. Respond in the same language the user is speaking.\n"
    "6. Do not repeat yourself. Do not pad responses with filler phrases."
)

# ─────────────────────────────────────────────────────────────────────────────
#  VAD + Whisper Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class VADWhisperPipeline:
    """
    Real-time voice pipeline:
      Microphone → WebRTC VAD → faster-whisper STT → text segments

    VAD gates Whisper — only speech frames are transcribed,
    eliminating hallucinations on silence and reducing CPU load.
    """

    SAMPLE_RATE    = 16_000
    VAD_FRAME_MS   = 30
    SILENCE_PAD_MS = 400
    MIN_SPEECH_MS  = 250

    def __init__(
        self,
        model_size: str     = "base.en",
        device: str         = "cpu",
        language: str       = "en",
        vad_aggressiveness: int = 2,
    ) -> None:
        self.model_size         = model_size
        self.device             = device
        self.language           = language
        self.vad_aggressiveness = vad_aggressiveness
        self._model             = None
        self._vad               = None

    def _lazy_init(self) -> None:
        if self._model is not None:
            return
        import webrtcvad
        from faster_whisper import WhisperModel

        log.info("Loading faster-whisper [%s] on %s ...", self.model_size, self.device)
        self._model = WhisperModel(
            self.model_size,
            device       = self.device,
            compute_type = "int8",
        )
        self._vad = webrtcvad.Vad(self.vad_aggressiveness)
        log.info("VAD + Whisper ready.")

    def transcribe_file(self, audio_path: str) -> str:
        """Transcribe a file (wav/mp3/ogg). Used for batch/testing."""
        self._lazy_init()
        segments, info = self._model.transcribe(
            audio_path,
            language       = self.language,
            beam_size      = 5,
            vad_filter     = True,
            vad_parameters = {
                "min_silence_duration_ms": self.SILENCE_PAD_MS,
                "speech_pad_ms": 200,
            },
        )
        text = " ".join(s.text.strip() for s in segments)
        log.info("Transcribed (%s): %s", info.language, text)
        return text.strip()

    def listen_microphone(self) -> Iterator[str]:
        """
        Blocking generator. Captures mic, applies VAD, yields
        transcribed utterances in real time.
        """
        import io
        import wave
        import pyaudio
        import webrtcvad

        self._lazy_init()

        pa          = pyaudio.PyAudio()
        frame_bytes = int(self.SAMPLE_RATE * self.VAD_FRAME_MS / 1000) * 2
        stream      = pa.open(
            format             = pyaudio.paInt16,
            channels           = 1,
            rate               = self.SAMPLE_RATE,
            input              = True,
            frames_per_buffer  = frame_bytes // 2,
        )

        log.info("Mic open. Listening (VAD aggressiveness=%d)...", self.vad_aggressiveness)

        RING_LEN      = int(self.SILENCE_PAD_MS / self.VAD_FRAME_MS)
        ring_buffer:  list[tuple[bytes, bool]] = []
        voiced_frames: list[bytes] = []
        triggered     = False

        try:
            while True:
                raw       = stream.read(frame_bytes // 2, exception_on_overflow=False)
                is_speech = self._vad.is_speech(raw[:frame_bytes], self.SAMPLE_RATE)

                if not triggered:
                    ring_buffer.append((raw, is_speech))
                    if len(ring_buffer) > RING_LEN:
                        ring_buffer.pop(0)
                    if sum(1 for _, s in ring_buffer if s) / RING_LEN > 0.75:
                        triggered     = True
                        voiced_frames = [f for f, _ in ring_buffer]
                        ring_buffer   = []
                else:
                    voiced_frames.append(raw)
                    ring_buffer.append((raw, is_speech))
                    if len(ring_buffer) > RING_LEN:
                        ring_buffer.pop(0)
                    if sum(1 for _, s in ring_buffer if not s) / RING_LEN > 0.90:
                        triggered   = False
                        ring_buffer = []

                        if len(voiced_frames) * self.VAD_FRAME_MS < self.MIN_SPEECH_MS:
                            voiced_frames = []
                            continue

                        buf = io.BytesIO()
                        with wave.open(buf, "wb") as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(self.SAMPLE_RATE)
                            wf.writeframes(b"".join(voiced_frames))
                        buf.seek(0)

                        segments, _ = self._model.transcribe(
                            buf, language=self.language, beam_size=3, vad_filter=False
                        )
                        text = " ".join(s.text.strip() for s in segments).strip()
                        if text:
                            yield text
                        voiced_frames = []
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()


# ─────────────────────────────────────────────────────────────────────────────
#  Intent Classifier  (3 tiers)
# ─────────────────────────────────────────────────────────────────────────────

_LOCAL_RE = re.compile(
    r"^(run|execute|open|launch|start|stop|kill|list|show|print|echo|cd|ls|pwd|"
    r"mkdir|rm|cp|mv|cat|grep|ping|curl|wget|git|pip|python3?|bash|sh|sudo|"
    r"systemctl|journalctl|apt|df|du|free|top|htop|ps|chmod|chown)\b",
    re.IGNORECASE,
)

# Threshold: prompts longer than this go straight to Titan
_TITAN_CHAR_THRESHOLD = 80

# Keywords that signal complex reasoning → always route to Titan
_TITAN_KEYWORDS = re.compile(
    r"\b("
    # Polish
    r"napisz|wygeneruj|stwórz|stwórz|wyjaśnij szczegółowo|przeanalizuj|"
    r"zrefaktoryzuj|zdebuguj|zoptymalizuj|porównaj|podsumuj|przetłumacz|"
    r"zaprojektuj|zaimplementuj|udowodnij|oblicz|wylicz|wylistuj wszystkie|"
    # English
    r"write|implement|create|generate|explain in detail|analyze|refactor|"
    r"debug|optimize|build|design|compare|summarize|translate|calculate|"
    r"list all|enumerate|step by step|how does|why does|what is the difference|"
    r"write a|build a|design a|give me a|show me how"
    r")\b",
    re.IGNORECASE,
)


def classify_intent(text: str) -> str:
    """
    Classify user input into one of three routing tiers.

    Returns: "local" | "ollama" | "titan"
    """
    stripped = text.strip()

    # Tier 1 — local shell
    if _LOCAL_RE.match(stripped):
        return "local"
    tokens = stripped.split()
    if len(tokens) <= 3 and all(t.islower() or t.startswith("-") for t in tokens):
        return "local"

    # Tier 3 — complex, force Titan
    if len(stripped) > _TITAN_CHAR_THRESHOLD:
        return "titan"
    if _TITAN_KEYWORDS.search(stripped):
        return "titan"

    # Tier 2 — default: fast Ollama 1B
    return "ollama"


# ─────────────────────────────────────────────────────────────────────────────
#  Local Command Executor
# ─────────────────────────────────────────────────────────────────────────────

def run_local_command(command: str, timeout: int = 30) -> str:
    log.info("LOCAL: %s", command)
    try:
        result = subprocess.run(
            shlex.split(command),
            capture_output = True,
            text           = True,
            timeout        = timeout,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            log.warning("Exit %d: %s", result.returncode, output[:200])
        return output or f"(exit {result.returncode})"
    except FileNotFoundError as exc:
        return f"Command not found: {exc}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s."


# ─────────────────────────────────────────────────────────────────────────────
#  Ollama Client  (Tier 2 — local 1B model)
#  Uses the official `ollama` Python library.
# ─────────────────────────────────────────────────────────────────────────────

class OllamaClient:
    """
    Wrapper around the `ollama` Python library for local 1B inference.

    The library talks to the Ollama daemon at the configured host
    (default: http://localhost:11434) and handles connection pooling
    internally. Falls back to Titan on any error.
    """

    def __init__(
        self,
        host: str  = "http://localhost:11434",
        model: str = "llama3.2:1b",
    ) -> None:
        self._model  = model
        self._client = ollama_lib.Client(host=host)
        self._online: Optional[bool] = None

    @property
    def model(self) -> str:
        return self._model

    def probe(self) -> bool:
        """
        Check if the Ollama daemon is reachable and the target model
        is already pulled. Caches the result for the session.
        """
        try:
            models = self._client.list()
            names  = [m.model for m in models.models]
            if not any(self._model in n for n in names):
                log.warning(
                    "Ollama model '%s' not found locally. "
                    "Run: ollama pull %s",
                    self._model, self._model,
                )
            self._online = True
        except Exception as exc:
            log.warning("Ollama unreachable: %s", exc)
            self._online = False
        log.info(
            "Ollama probe: %s | model=%s",
            "online" if self._online else "OFFLINE",
            self._model,
        )
        return self._online

    def generate(self, prompt: str, system: str = MOBIUS_SYSTEM_PROMPT) -> str:
        """
        Blocking generate call via the ollama library.
        Retry once on transient connection errors.
        Returns the response text, or raises RuntimeError on failure.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                response = self._client.generate(
                    model   = self._model,
                    prompt  = prompt,
                    system  = system,
                    stream  = False,
                    options = {
                        "temperature":    0.3,
                        "top_p":          0.85,
                        "top_k":          40,
                        "repeat_penalty": 1.2,
                        "num_predict":    512,
                    },
                )
                return response.response.strip()
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"Ollama generate failed: {exc}") from exc
        raise RuntimeError(f"Ollama generate failed: {last_exc}") from last_exc

    def close(self) -> None:
        pass  # ollama.Client manages its own session lifecycle


# ─────────────────────────────────────────────────────────────────────────────
#  Titan gRPC Client  (Tier 3 — Node 2 RTX 5060 Ti)
# ─────────────────────────────────────────────────────────────────────────────

class TitanClient:
    """
    Persistent gRPC channel to Node 2 (Windows/Titan).
    Used for complex queries that exceed Ollama's capability.
    """

    def __init__(self, host: str, port: int) -> None:
        self._target  = f"{host}:{port}"
        self._channel: Optional[grpc.Channel] = None
        self._stub:    Optional[mobius_pb2_grpc.TitanServiceStub] = None

    def connect(self) -> None:
        opts = [
            ("grpc.keepalive_time_ms",              30_000),
            ("grpc.keepalive_timeout_ms",           10_000),
            ("grpc.keepalive_permit_without_calls", True),
            ("grpc.http2.max_pings_without_data",   0),
            ("grpc.max_send_message_length",        512 * 1024 * 1024),
            ("grpc.max_receive_message_length",     512 * 1024 * 1024),
        ]
        self._channel = grpc.insecure_channel(self._target, options=opts)
        self._stub    = mobius_pb2_grpc.TitanServiceStub(self._channel)
        log.info("Titan channel opened → %s", self._target)

    def close(self) -> None:
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub    = None

    def health_check(self) -> mobius_pb2.HealthResponse:
        return self._stub.HealthCheck(
            mobius_pb2.HealthRequest(include_vram_detail=True),
            timeout=5,
        )

    def infer(
        self,
        prompt: str,
        model_id: str       = "",
        max_new_tokens: int = 512,
        temperature: float  = 0.7,
        top_p: float        = 0.9,
    ) -> mobius_pb2.InferResponse:
        req = mobius_pb2.InferRequest(
            prompt            = prompt,
            model_id          = model_id,
            max_new_tokens    = max_new_tokens,
            temperature       = temperature,
            top_p             = top_p,
            use_system_prompt = True,
            system_prompt     = MOBIUS_SYSTEM_PROMPT,
            sampling          = mobius_pb2.SamplingParams(
                repetition_penalty = 1.1,
                top_k              = 50,
                do_sample          = True,
            ),
        )
        log.info("Infer → Titan [%s] max_tokens=%d", self._target, max_new_tokens)
        resp = self._stub.Infer(req, timeout=300)
        log.info(
            "Titan response | tokens=%d | %.1f ms | purged=%s",
            resp.tokens_generated, resp.inference_time_ms, resp.purged,
        )
        return resp

    def infer_stream(
        self,
        prompt: str,
        model_id: str       = "",
        max_new_tokens: int = 512,
        temperature: float  = 0.7,
    ) -> Iterator[str]:
        req = mobius_pb2.InferRequest(
            prompt         = prompt,
            model_id       = model_id,
            max_new_tokens = max_new_tokens,
            temperature    = temperature,
            stream         = True,
        )
        for chunk in self._stub.InferStream(req, timeout=300):
            if not chunk.done:
                yield chunk.token
            else:
                log.info(
                    "Stream done | tokens=%d | vram_after=%.1f MB",
                    chunk.index, chunk.vram_used_mb,
                )

    def purge_vram(self) -> mobius_pb2.PurgeResponse:
        return self._stub.PurgeVRAM(
            mobius_pb2.PurgeRequest(force_gc=True), timeout=30
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Sentinel Node — Main Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class ConversationHistory:
    """
    Rolling window of conversation turns for context injection.
    Keeps last N exchanges and formats them into a prompt prefix.
    """

    def __init__(self, max_turns: int = 6) -> None:
        self._turns:     list[tuple[str, str]] = []  # (user, assistant)
        self._max_turns  = max_turns

    def add(self, user: str, assistant: str) -> None:
        self._turns.append((user, assistant))
        if len(self._turns) > self._max_turns:
            self._turns.pop(0)

    def format_for_prompt(self, current_input: str) -> str:
        """Return a prompt string with history prepended."""
        if not self._turns:
            return current_input
        lines = []
        for u, a in self._turns:
            lines.append(f"User: {u}")
            lines.append(f"MOBIUS: {a}")
        lines.append(f"User: {current_input}")
        lines.append("MOBIUS:")
        return "\n".join(lines)

    def clear(self) -> None:
        self._turns.clear()

    def __len__(self) -> int:
        return len(self._turns)


class SentinelNode:
    """
    Master process. Routes input through 3 tiers:
      local → Ollama (1B, fast) → Titan (7B+, complex)

    Modes: text (REPL), mic (live microphone + VAD)
    """

    def __init__(
        self,
        titan_host:    str,
        titan_port:    int,
        ollama_host:   str  = "http://localhost:11434",
        ollama_model:  str  = "llama3.2:1b",
        whisper_model: str  = "base.en",
        language:      str  = "en",
        mode:          str  = "text",
        history_turns: int  = 6,
    ) -> None:
        self._titan  = TitanClient(titan_host, titan_port)
        self._ollama = OllamaClient(host=ollama_host, model=ollama_model)
        self._vad_asr = VADWhisperPipeline(
            model_size = whisper_model,
            device     = "cpu",
            language   = language,
        )
        self._mode         = mode
        self._ollama_alive = False
        self._history      = ConversationHistory(max_turns=history_turns)

    def start(self) -> None:
        self._titan.connect()
        self._ollama_alive = self._ollama.probe()
        self._probe_titan()

        if self._mode == "mic":
            self._run_mic_loop()
        elif self._mode == "text":
            self._run_text_repl()
        else:
            log.error("Unknown mode: %s", self._mode)

    def _probe_titan(self) -> None:
        try:
            h = self._titan.health_check()
            log.info(
                "Titan online | GPU=%s | VRAM=%.0f/%.0f MB | model=%s",
                h.gpu_name, h.vram_used_mb, h.vram_total_mb,
                h.model_id or "<idle>",
            )
        except grpc.RpcError as exc:
            log.warning("Titan unreachable (%s). Complex queries will fail.", exc.code())

    def _dispatch(self, text: str) -> str:
        """
        Route text through the 3-tier pipeline.
        Injects conversation history for LLM tiers.
        Returns the response string.
        """
        tier = classify_intent(text)
        log.info("Tier: %-6s | %s", tier.upper(), text[:80])

        if tier == "local":
            result = run_local_command(text)
            self._history.add(text, result)
            return result

        # Build prompt with conversation history for LLM tiers
        prompt_with_history = self._history.format_for_prompt(text)

        if tier == "ollama":
            if self._ollama_alive:
                try:
                    result = self._ollama.generate(prompt_with_history)
                    self._history.add(text, result)
                    return result
                except RuntimeError as exc:
                    log.warning("Ollama failed (%s), falling back to Titan.", exc)
            else:
                log.info("Ollama offline, routing directly to Titan.")

        # tier == "titan" or Ollama fallback
        try:
            resp = self._titan.infer(
                prompt         = prompt_with_history,
                max_new_tokens = 1024,
                temperature    = 0.4,   # obniżone dla mniejszej liczby halucynacji
            )
            self._history.add(text, resp.text)
            return resp.text
        except grpc.RpcError as exc:
            return f"[MOBIUS ERROR: Titan unreachable — {exc.code()} {exc.details()}]"

    # ── REPL ─────────────────────────────────────────────────────────────────

    def _run_text_repl(self) -> None:
        ollama_status = f"{self._ollama.model} online" if self._ollama_alive else "offline"
        print(f"\nMOBIUS v{SENTINEL_VERSION} | Ollama: {ollama_status}")
        print("Commands: !health  !purge  !clear  !tier <text>  exit\n")

        try:
            while True:
                try:
                    text = input("MOBIUS › ").strip()
                except EOFError:
                    break

                if not text:
                    continue

                if text.lower() in {"exit", "quit", "q"}:
                    break

                if text.lower() == "!health":
                    self._cmd_health()
                    continue

                if text.lower() == "!clear":
                    self._history.clear()
                    print("[Pamięć rozmowy wyczyszczona]")
                    continue

                if text.lower() == "!purge":
                    r = self._titan.purge_vram()
                    print(f"[VRAM purged] freed={r.freed_mb:.1f} MB | after={r.vram_after_mb:.1f} MB")
                    continue

                if text.lower().startswith("!tier "):
                    sample = text[6:].strip()
                    print(f"→ {classify_intent(sample).upper()}")
                    continue

                t0     = time.perf_counter()
                result = self._dispatch(text)
                ms     = (time.perf_counter() - t0) * 1000
                print(f"\n{result}\n[{ms:.0f} ms]\n")

        except KeyboardInterrupt:
            pass
        finally:
            self._titan.close()
            self._ollama.close()
            print("MOBIUS offline.")

    def _cmd_health(self) -> None:
        print(f"  Ollama : {'online' if self._ollama_alive else 'OFFLINE'} ({self._ollama.model})")
        try:
            h = self._titan.health_check()
            print(
                f"  Titan  : online | {h.gpu_name} | "
                f"VRAM {h.vram_used_mb:.0f}/{h.vram_total_mb:.0f} MB | "
                f"model={h.model_id or '<idle>'} | uptime={h.uptime_seconds}s"
            )
        except grpc.RpcError as exc:
            print(f"  Titan  : OFFLINE ({exc.code()})")

    # ── Mic loop ─────────────────────────────────────────────────────────────

    def _run_mic_loop(self) -> None:
        print(f"\nMOBIUS v{SENTINEL_VERSION} | mic/VAD mode | Ctrl-C to stop\n")
        try:
            for utterance in self._vad_asr.listen_microphone():
                print(f"[YOU]    {utterance}")
                result = self._dispatch(utterance)
                print(f"[MOBIUS] {result}\n")
        except KeyboardInterrupt:
            pass
        finally:
            self._titan.close()
            self._ollama.close()
            print("MOBIUS offline.")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="MOBIUS Sentinel — Ubuntu Server 24.04")
    parser.add_argument(
        "--titan-host",
        default=os.environ.get("TITAN_HOST", "192.168.1.249"),
    )
    parser.add_argument(
        "--titan-port",
        type=int,
        default=int(os.environ.get("TITAN_PORT", "50051")),
    )
    parser.add_argument(
        "--ollama-host",
        default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    )
    parser.add_argument(
        "--ollama-model",
        default=os.environ.get("OLLAMA_MODEL", "llama3.2:1b"),
    )
    parser.add_argument(
        "--whisper-model",
        default=os.environ.get("WHISPER_MODEL", "base.en"),
        choices=["tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "large-v3"],
    )
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--mode",
        default=os.environ.get("MOBIUS_MODE", "text"),
        choices=["text", "mic"],
    )
    args = parser.parse_args()

    node = SentinelNode(
        titan_host    = args.titan_host,
        titan_port    = args.titan_port,
        ollama_host   = args.ollama_host,
        ollama_model  = args.ollama_model,
        whisper_model = args.whisper_model,
        language      = args.language,
        mode          = args.mode,
    )
    node.start()


if __name__ == "__main__":
    main()
