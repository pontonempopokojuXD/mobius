"""
MOBIUS Titan Client — gRPC klient do Node 2 (Windows/RTX)
Używany przez GUI gdy backend = Titan.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator, Optional

# generated stubs
sys.path.insert(0, str(Path(__file__).resolve().parent / "generated"))

try:
    import grpc
    import mobius_pb2
    import mobius_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False

PONTIFEX_SYSTEM_PROMPT = """Jesteś Pontifex Rex — główny architekt systemu MOBIUS.
Styl: konkretny, lapidarny. Bez infantylizmu.
Używaj metafor: kuźnia, build, debuff, pipeline.
Odpowiadaj wyłącznie po polsku.
Bądź zwięzły. Każde słowo ma wagę."""


def titan_available(host: str, port: int, timeout: float = 3) -> bool:
    """Sprawdź dostępność Titan."""
    if not GRPC_AVAILABLE:
        return False
    channel = grpc.insecure_channel(f"{host}:{port}")
    try:
        stub = mobius_pb2_grpc.TitanServiceStub(channel)
        stub.HealthCheck(mobius_pb2.HealthRequest(include_vram_detail=True), timeout=timeout)
        return True
    except Exception:
        return False
    finally:
        channel.close()


def titan_infer(
    host: str,
    port: int,
    prompt: str,
    system: str = PONTIFEX_SYSTEM_PROMPT,
    model_id: str = "",
    max_new_tokens: int = 512,
    temperature: float = 0.7,
    timeout: float = 300,
) -> tuple[str, float]:
    """Inferencja blocking. Zwraca (text, elapsed_ms)."""
    if not GRPC_AVAILABLE:
        return "[gRPC niedostępny: pip install grpcio]", 0.0
    channel = grpc.insecure_channel(f"{host}:{port}")
    try:
        stub = mobius_pb2_grpc.TitanServiceStub(channel)
        req = mobius_pb2.InferRequest(
            prompt=prompt,
            model_id=model_id,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.9,
            use_system_prompt=True,
            system_prompt=system,
            sampling=mobius_pb2.SamplingParams(
                repetition_penalty=1.1,
                top_k=50,
                do_sample=True,
            ),
        )
        resp = stub.Infer(req, timeout=timeout)
        return resp.text.strip(), resp.inference_time_ms
    except grpc.RpcError as e:
        return f"[Titan: {e.code()} {e.details()}]", 0.0
    except Exception as e:
        return f"[Titan: {e}]", 0.0
    finally:
        channel.close()


def titan_infer_stream(
    host: str,
    port: int,
    prompt: str,
    system: str = PONTIFEX_SYSTEM_PROMPT,
    model_id: str = "",
    max_new_tokens: int = 512,
    temperature: float = 0.7,
    timeout: float = 300,
) -> Iterator[tuple[str, bool]]:
    """Streaming inferencja. Yields (token, done)."""
    if not GRPC_AVAILABLE:
        yield "[gRPC niedostępny]", True
        return
    channel = grpc.insecure_channel(f"{host}:{port}")
    try:
        stub = mobius_pb2_grpc.TitanServiceStub(channel)
        req = mobius_pb2.InferRequest(
            prompt=prompt,
            model_id=model_id,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.9,
            use_system_prompt=True,
            system_prompt=system,
            stream=True,
            sampling=mobius_pb2.SamplingParams(
                repetition_penalty=1.1,
                top_k=50,
                do_sample=True,
            ),
        )
        for chunk in stub.InferStream(req, timeout=timeout):
            if chunk.token:
                yield chunk.token, chunk.done
            if chunk.done:
                break
    except Exception as e:
        yield f"[Titan: {e}]", True
    finally:
        channel.close()
