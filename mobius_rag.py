"""
MOBIUS RAG — Baza wiedzy (Retrieval-Augmented Generation)
ChromaDB + embeddingi do semantycznego wyszukiwania.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

MOBIUS_ROOT = Path(__file__).resolve().parent
RAG_PERSIST_DIR = MOBIUS_ROOT / "mobius_rag_db"

CHROMA_AVAILABLE = False
_embedding_fn = None
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
    try:
        from chromadb.utils import embedding_functions
        _embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    except Exception:
        _embedding_fn = None
except Exception:
    pass

_client = None


def _get_client():
    if not CHROMA_AVAILABLE:
        return None
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(RAG_PERSIST_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_collection(name: str):
    client = _get_client()
    if not client:
        return None
    kwargs = {"metadata": {"hnsw:space": "cosine"}}
    if _embedding_fn:
        kwargs["embedding_function"] = _embedding_fn
    return client.get_or_create_collection(name, **kwargs)


def rag_add(text: str, metadata: Optional[dict] = None) -> bool:
    """Dodaj fragment do bazy wiedzy."""
    coll = _get_collection("mobius_knowledge")
    if not coll:
        return False
    try:
        doc_id = f"doc_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"
        coll.add(documents=[text], ids=[doc_id], metadatas=[metadata or {}])
        return True
    except Exception:
        return False


def rag_add_autonomous(text: str, metadata: Optional[dict] = None) -> bool:
    """Dodaj do osobnej kolekcji autonomicznej (nie zaśmieca recall_context)."""
    coll = _get_collection("mobius_autonomous")
    if not coll:
        return False
    try:
        doc_id = f"auto_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"
        coll.add(documents=[text], ids=[doc_id], metadatas=[metadata or {}])
        return True
    except Exception:
        return False


def rag_search(query: str, n_results: int = 5) -> list[str]:
    """Wyszukaj podobne fragmenty (semantycznie)."""
    coll = _get_collection("mobius_knowledge")
    if not coll:
        return []
    try:
        results = coll.query(query_texts=[query], n_results=n_results)
        docs = results.get("documents", [[]])
        return docs[0] if docs else []
    except Exception:
        return []


def rag_add_from_file(path: str) -> tuple[int, str]:
    """Dodaj plik tekstowy do bazy (po liniach/paragrafach). Zwraca (liczba_chunków, status)."""
    coll = _get_collection("mobius_knowledge")
    if not coll:
        return 0, "ChromaDB niedostępny: pip install chromadb"
    p = Path(path)
    if not p.is_absolute():
        p = MOBIUS_ROOT / path
    if not p.exists():
        return 0, f"Plik nie istnieje: {p}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 50]
        if not chunks:
            chunks = [c.strip() for c in text.split("\n") if len(c.strip()) > 30]
        ids = [f"{p.name}_{i}" for i in range(len(chunks))]
        coll.add(documents=chunks, ids=ids, metadatas=[{"source": str(p)}] * len(chunks))
        return len(chunks), f"Dodano {len(chunks)} fragmentów z {p.name}"
    except Exception as e:
        return 0, str(e)
