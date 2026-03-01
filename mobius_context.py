"""MOBIUS Context Window — smart context scoring dla prompt budgetu."""

from __future__ import annotations


def build_context(
    messages: list[dict],
    current_query: str = "",
    max_tokens: int = 3000,
) -> list[dict]:
    """
    Wybierz wiadomości mieszczące się w budżecie tokenów.
    Zawsze zachowuje ostatnie 4 (recent anchor).
    Starsze: score = recency*0.4 + length*0.3 + keyword*0.3
    """
    if not messages:
        return []

    recent_count = 4
    if len(messages) <= recent_count:
        return messages[:]

    recent = messages[-recent_count:]
    candidates = messages[:-recent_count]

    if not candidates:
        return messages[:]

    query_words = set(current_query.lower().split()) if current_query.strip() else set()
    n = len(candidates)

    scored: list[tuple[float, int, dict, int]] = []
    for i, msg in enumerate(candidates):
        content = msg.get("content", "")
        recency = i / max(n - 1, 1)
        length_score = 1.0 - min(len(content) / 2000.0, 1.0)
        if query_words:
            msg_words = set(content.lower().split())
            overlap = len(query_words & msg_words) / max(len(query_words), 1)
            keyword_score = min(overlap, 1.0)
            score = recency * 0.4 + length_score * 0.3 + keyword_score * 0.3
        else:
            score = recency
        tokens = len(content) // 4 + 1
        scored.append((score, i, msg, tokens))

    scored.sort(key=lambda x: x[0], reverse=True)

    recent_tokens = sum(len(m.get("content", "")) // 4 + 1 for m in recent)
    budget = max_tokens - recent_tokens

    selected: list[tuple[int, dict]] = []
    for score, idx, msg, tokens in scored:
        if budget <= 0:
            break
        selected.append((idx, msg))
        budget -= tokens

    selected.sort(key=lambda x: x[0])
    return [m for _, m in selected] + recent
