"""
MOBIUS – Titan Node (Node 2 / Windows)
RTX 5060 Ti | gRPC inference server with on-demand model loading and hard VRAM purge.

Start:  python titan_node.py [--host 0.0.0.0] [--port 50051]
"""

from __future__ import annotations

import argparse
import gc
import logging
import os
import sys
import time
from concurrent import futures
from pathlib import Path
from typing import Iterator, Optional

import grpc
import psutil
import torch

# ── Generated gRPC stubs (run: python -m grpc_tools.protoc ...) ──────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "generated"))
import mobius_pb2
import mobius_pb2_grpc

# ─────────────────────────────────────────────────────────────────────────────
TITAN_VERSION = "1.0.0"
DEFAULT_HOST  = "0.0.0.0"
DEFAULT_PORT  = 50051

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TITAN] %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("titan")

# ─────────────────────────────────────────────────────────────────────────────
#  VRAM Utilities
# ─────────────────────────────────────────────────────────────────────────────

def vram_used_mb() -> float:
    if not torch.cuda.is_available():
        return 0.0
    return torch.cuda.memory_allocated() / 1024**2


def vram_reserved_mb() -> float:
    if not torch.cuda.is_available():
        return 0.0
    return torch.cuda.memory_reserved() / 1024**2


def vram_total_mb() -> float:
    if not torch.cuda.is_available():
        return 0.0
    props = torch.cuda.get_device_properties(0)
    return props.total_memory / 1024**2


def gpu_name() -> str:
    if not torch.cuda.is_available():
        return "N/A"
    return torch.cuda.get_device_name(0)


# ─────────────────────────────────────────────────────────────────────────────
#  Hard VRAM Purge  ← Core requirement
# ─────────────────────────────────────────────────────────────────────────────

def hard_vram_purge(model_ref: Optional[object] = None) -> tuple[float, float]:
    """
    Perform a multi-stage VRAM purge targeting 0% idle usage.

    Stages:
      1. Delete model/tokenizer references (if provided)
      2. gc.collect()           – free Python-side objects
      3. torch.cuda.empty_cache() – release PyTorch memory pool back to OS
      4. torch.cuda.synchronize() – flush CUDA stream; blocks until GPU is idle
      5. Second gc.collect()    – catch circular refs freed by CUDA callbacks

    Returns (vram_before_mb, vram_after_mb).
    """
    before = vram_reserved_mb()
    log.info("VRAM purge initiated | reserved=%.1f MB", before)

    # Stage 1 – drop model references
    if model_ref is not None:
        del model_ref

    # Stage 2 – Python GC pass 1
    gc.collect()

    # Stage 3 – Return CUDA memory pool to OS allocator
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # Stage 4 – Synchronise CUDA stream (ensures all ops complete)
    if torch.cuda.is_available():
        torch.cuda.synchronize()

    # Stage 5 – Python GC pass 2 (CUDA callbacks may have freed more)
    gc.collect()

    after = vram_reserved_mb()
    freed = max(0.0, before - after)
    log.info(
        "VRAM purge complete | before=%.1f MB → after=%.1f MB | freed=%.1f MB",
        before, after, freed,
    )
    return before, after


# ─────────────────────────────────────────────────────────────────────────────
#  Model Manager  (lazy load / eager unload)
# ─────────────────────────────────────────────────────────────────────────────

class ModelManager:
    """
    Manages a single LLM instance on GPU.

    Policy:
      • Model is loaded ONLY when an inference request arrives.
      • After every inference the model is PURGED from VRAM.
      • Warm-up call pre-loads the model without inference.
    """

    def __init__(self) -> None:
        self._model     = None
        self._tokenizer = None
        self._model_id  = ""
        self._loaded    = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def model_id(self) -> str:
        return self._model_id

    def load(
        self,
        model_id: str,
        use_flash_attn: bool = True,
        use_4bit: bool = True,
    ) -> float:
        """
        Load model with BitsAndBytes 4-bit quantisation and optional FlashAttention-3.
        Returns load time in milliseconds.
        """
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if self._loaded and self._model_id == model_id:
            log.info("Model already loaded: %s", model_id)
            return 0.0

        if self._loaded:
            log.info("Unloading previous model: %s", self._model_id)
            self.unload()

        log.info("Loading model: %s | 4bit=%s flash_attn=%s", model_id, use_4bit, use_flash_attn)
        t0 = time.perf_counter()

        bnb_config = None
        if use_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )

        if use_flash_attn:
            try:
                import flash_attn  # noqa: F401
                attn_impl = "flash_attention_2"
            except ImportError:
                log.warning("flash-attn nie jest zainstalowany — używam eager attention.")
                attn_impl = "eager"
        else:
            attn_impl = "eager"

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_id, trust_remote_code=True
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id,
            quantization_config=bnb_config,
            device_map="cuda:0",
            torch_dtype=torch.bfloat16,
            attn_implementation=attn_impl,
            trust_remote_code=True,
        )
        self._model.eval()

        # ── Triton kernel patches (RMSNorm + SwiGLU) ─────────────────────────
        try:
            from triton_kernels import patch_model
            counts = patch_model(self._model, verbose=False)
            if any(v > 0 for v in counts.values()):
                log.info("Triton patches applied: %s", counts)
        except Exception as exc:
            log.warning("Triton patching skipped: %s", exc)
        # ─────────────────────────────────────────────────────────────────────

        self._model_id = model_id
        self._loaded   = True
        elapsed_ms     = (time.perf_counter() - t0) * 1000
        log.info(
            "Model loaded in %.1f ms | VRAM=%.1f MB",
            elapsed_ms, vram_used_mb()
        )
        return elapsed_ms

    def unload(self) -> tuple[float, float]:
        """Unload model and perform hard VRAM purge."""
        model_ref  = self._model
        self._model     = None
        self._tokenizer = None
        self._model_id  = ""
        self._loaded    = False
        return hard_vram_purge(model_ref)

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        min_p: float = 0.0,
        do_sample: bool = True,
        stop_sequences: list[str] | None = None,
    ) -> tuple[str, int, int]:
        """
        Run inference. Returns (generated_text, prompt_tokens, new_tokens).
        Caller is responsible for calling unload() after this.
        """
        if not self._loaded:
            raise RuntimeError("No model loaded. Call load() first.")

        inputs = self._tokenizer(prompt, return_tensors="pt").to("cuda:0")
        prompt_len = inputs["input_ids"].shape[-1]

        gen_kwargs: dict = dict(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature if do_sample else 1.0,
            top_p=top_p if do_sample else 1.0,
            top_k=top_k if do_sample else 0,
            repetition_penalty=repetition_penalty,
            do_sample=do_sample,
            pad_token_id=self._tokenizer.eos_token_id,
        )

        if stop_sequences:
            from transformers import StoppingCriteria, StoppingCriteriaList

            class StopOnTokens(StoppingCriteria):
                def __init__(self, stop_ids: list[list[int]]):
                    self.stop_ids = stop_ids
                def __call__(self, input_ids, scores, **_):
                    for sid in self.stop_ids:
                        if input_ids[0][-len(sid):].tolist() == sid:
                            return True
                    return False

            stop_ids = [
                self._tokenizer.encode(s, add_special_tokens=False)
                for s in stop_sequences
            ]
            gen_kwargs["stopping_criteria"] = StoppingCriteriaList([StopOnTokens(stop_ids)])

        with torch.inference_mode():
            output_ids = self._model.generate(**gen_kwargs)

        new_ids   = output_ids[0][prompt_len:]
        new_tokens = len(new_ids)
        text       = self._tokenizer.decode(new_ids, skip_special_tokens=True)

        return text, prompt_len, new_tokens

    def generate_stream(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        do_sample: bool = True,
    ) -> Iterator[str]:
        """
        Streaming token generator using TextIteratorStreamer.
        Yields decoded token strings one by one.
        """
        import threading
        from transformers import TextIteratorStreamer

        if not self._loaded:
            raise RuntimeError("No model loaded.")

        inputs = self._tokenizer(prompt, return_tensors="pt").to("cuda:0")
        streamer = TextIteratorStreamer(
            self._tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        gen_kwargs = dict(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature if do_sample else 1.0,
            top_p=top_p if do_sample else 1.0,
            do_sample=do_sample,
            pad_token_id=self._tokenizer.eos_token_id,
            streamer=streamer,
        )

        thread = threading.Thread(
            target=self._model.generate,
            kwargs=gen_kwargs,
            daemon=True,
        )
        with torch.inference_mode():
            thread.start()
            for token_text in streamer:
                yield token_text
            thread.join()


# ─────────────────────────────────────────────────────────────────────────────
#  gRPC Service Implementation
# ─────────────────────────────────────────────────────────────────────────────

class TitanServicer(mobius_pb2_grpc.TitanServiceServicer):

    def __init__(self) -> None:
        self._manager    = ModelManager()
        self._start_time = time.time()
        log.info("TitanServicer initialised | GPU: %s | VRAM: %.0f MB total",
                 gpu_name(), vram_total_mb())

    # ── HealthCheck ──────────────────────────────────────────────────────────

    def HealthCheck(self, request, context):
        used  = vram_used_mb()
        total = vram_total_mb()
        return mobius_pb2.HealthResponse(
            online        = True,
            model_loaded  = self._manager.loaded,
            vram_used_mb  = used,
            vram_total_mb = total,
            vram_free_mb  = total - used,
            gpu_name      = gpu_name(),
            model_id      = self._manager.model_id,
            titan_version = TITAN_VERSION,
            uptime_seconds= int(time.time() - self._start_time),
        )

    # ── PurgeVRAM ────────────────────────────────────────────────────────────

    def PurgeVRAM(self, request, context):
        before, after = self._manager.unload() if self._manager.loaded \
                        else hard_vram_purge()
        return mobius_pb2.PurgeResponse(
            success       = True,
            vram_before_mb= before,
            vram_after_mb = after,
            freed_mb      = max(0.0, before - after),
        )

    # ── WarmUp ───────────────────────────────────────────────────────────────

    def WarmUp(self, request, context):
        try:
            load_ms = self._manager.load(
                model_id       = request.model_id,
                use_flash_attn = request.use_flash_attn,
                use_4bit       = request.use_4bit,
            )
            return mobius_pb2.WarmUpResponse(
                success      = True,
                load_time_ms = load_ms,
                vram_used_mb = vram_used_mb(),
            )
        except Exception as exc:
            log.exception("WarmUp failed")
            return mobius_pb2.WarmUpResponse(success=False, error=str(exc))

    # ── Infer (blocking) ─────────────────────────────────────────────────────

    def Infer(self, request, context):
        model_id = request.model_id or _default_model_id()
        log.info("Infer | model=%s | max_tokens=%d", model_id, request.max_new_tokens or 512)

        try:
            self._manager.load(
                model_id       = model_id,
                use_flash_attn = True,
                use_4bit       = True,
            )
        except Exception as exc:
            context.abort(grpc.StatusCode.INTERNAL, f"Model load failed: {exc}")
            return

        vram_pre  = vram_used_mb()
        t0        = time.perf_counter()

        sampling = request.sampling
        try:
            text, prompt_tokens, new_tokens = self._manager.generate(
                prompt             = _build_prompt(request),
                max_new_tokens     = request.max_new_tokens or 512,
                temperature        = request.temperature or 0.7,
                top_p              = request.top_p or 0.9,
                top_k              = sampling.top_k or 50,
                repetition_penalty = sampling.repetition_penalty or 1.1,
                min_p              = sampling.min_p or 0.0,
                do_sample          = sampling.do_sample if sampling.HasField("do_sample") else True,
                stop_sequences     = list(request.stop_sequences) or None,
            )
        except Exception as exc:
            log.exception("Inference failed")
            self._manager.unload()
            context.abort(grpc.StatusCode.INTERNAL, f"Inference failed: {exc}")
            return

        elapsed_ms = (time.perf_counter() - t0) * 1000
        vram_snap  = vram_used_mb()

        # ── HARD PURGE ────────────────────────────────────────────────────────
        self._manager.unload()
        # ─────────────────────────────────────────────────────────────────────

        stats = mobius_pb2.NodeStats(
            cpu_percent    = psutil.cpu_percent(),
            ram_used_mb    = psutil.virtual_memory().used / 1024**2,
            gpu_util_percent= _gpu_util(),
        )

        log.info(
            "Infer complete | tokens=%d | time=%.1f ms | purged=True",
            new_tokens, elapsed_ms,
        )

        return mobius_pb2.InferResponse(
            text             = text,
            tokens_generated = new_tokens,
            tokens_prompt    = prompt_tokens,
            inference_time_ms= elapsed_ms,
            vram_used_mb     = vram_snap,
            purged           = True,
            stats            = stats,
        )

    # ── InferStream (token-by-token) ─────────────────────────────────────────

    def InferStream(self, request, context):
        model_id = request.model_id or _default_model_id()
        log.info("InferStream | model=%s", model_id)

        try:
            self._manager.load(model_id=model_id, use_flash_attn=True, use_4bit=True)
        except Exception as exc:
            context.abort(grpc.StatusCode.INTERNAL, f"Model load failed: {exc}")
            return

        index = 0
        try:
            for token_text in self._manager.generate_stream(
                prompt         = _build_prompt(request),
                max_new_tokens = request.max_new_tokens or 512,
                temperature    = request.temperature or 0.7,
                top_p          = request.top_p or 0.9,
            ):
                yield mobius_pb2.InferChunk(
                    token = token_text,
                    index = index,
                    done  = False,
                )
                index += 1
        except Exception as exc:
            log.exception("Stream inference failed")
            self._manager.unload()
            context.abort(grpc.StatusCode.INTERNAL, str(exc))
            return

        vram_snap = vram_used_mb()

        # ── HARD PURGE ────────────────────────────────────────────────────────
        self._manager.unload()
        # ─────────────────────────────────────────────────────────────────────

        yield mobius_pb2.InferChunk(
            token        = "",
            index        = index,
            done         = True,
            vram_used_mb = vram_snap,
        )
        log.info("InferStream complete | tokens=%d | purged=True", index)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _default_model_id() -> str:
    return os.environ.get("TITAN_DEFAULT_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")


def _build_prompt(request: mobius_pb2.InferRequest) -> str:
    if request.use_system_prompt and request.system_prompt:
        return f"<s>[INST] <<SYS>>\n{request.system_prompt}\n<</SYS>>\n\n{request.prompt} [/INST]"
    return request.prompt


def _gpu_util() -> float:
    """Best-effort GPU utilisation percentage via pynvml."""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util   = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return float(util.gpu)
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  Server Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

def serve(host: str, port: int) -> None:
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4),
        options=[
            ("grpc.max_send_message_length",    512 * 1024 * 1024),
            ("grpc.max_receive_message_length", 512 * 1024 * 1024),
            ("grpc.keepalive_time_ms",          30_000),
            ("grpc.keepalive_timeout_ms",       10_000),
            ("grpc.keepalive_permit_without_calls", True),
        ],
    )
    mobius_pb2_grpc.add_TitanServiceServicer_to_server(TitanServicer(), server)
    addr = f"{host}:{port}"
    server.add_insecure_port(addr)
    server.start()
    log.info("Titan Node listening on %s", addr)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        log.info("Shutting down Titan Node...")
        server.stop(grace=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MOBIUS Titan Node – Windows/RTX")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    serve(args.host, args.port)
