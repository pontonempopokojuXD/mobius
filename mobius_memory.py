"""
MOBIUS Episodic Memory — indeksowanie sesji w RAG i przywoływanie kontekstu.
"""

from __future__ import annotations

from datetime import datetime

try:
    from mobius_rag import rag_add, _get_client, _embedding_fn
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False

    def rag_add(text: str, metadata: dict | None = None) -> bool:  # type: ignore[misc]
        return False

    def _get_client():  # type: ignore[misc]
        return None

    _embedding_fn = None  # type: ignore[assignment]


def generate_session_id() -> str:
    return datetime.now().strftime("session_%Y%m%d_%H%M%S")


def auto_index_session(messages: list[dict], session_id: str) -> int:
    """Chunk session messages into 5-message windows and index in RAG."""
    if not messages:
        return 0
    chunk_size = 5
    indexed = 0
    for i in range(0, len(messages), chunk_size):
        chunk = messages[i : i + chunk_size]
        text = "\n".join(
            f"{'Użytkownik' if m.get('role') == 'user' else 'MOBIUS'}: {m.get('content', '')}"
            for m in chunk
        )
        if not text.strip():
            continue
        meta = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "type": "episode",
        }
        if rag_add(text, meta):
            indexed += 1
    return indexed


def recall_context(query: str, n: int = 3) -> str:
    """Search RAG for relevant past episodes, formatted with timestamp."""
    if not _RAG_AVAILABLE:
        return ""
    try:
        client = _get_client()
        if not client:
            return ""
        kwargs: dict = {"metadata": {"hnsw:space": "cosine"}}
        if _embedding_fn:
            kwargs["embedding_function"] = _embedding_fn
        coll = client.get_or_create_collection("mobius_knowledge", **kwargs)
        results = coll.query(query_texts=[query], n_results=n)
        docs: list[str] = (results.get("documents") or [[]])[0]
        metas: list[dict] = (results.get("metadatas") or [[]])[0]
        if not docs:
            return ""
        parts: list[str] = []
        for doc, meta in zip(docs, metas):
            ts = (meta or {}).get("timestamp", "")
            if ts:
                try:
                    date = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date = ts[:10]
            else:
                date = "poprzednia sesja"
            parts.append(f"[Pamięć z {date}]: {doc}")
        return "\n".join(parts)
    except Exception:
        return ""
