"""AI price suggestion for publishers: rate how unique a piece of content is, map that to a price."""

import re

from app.services import llm
from app.services.license_core import longest_common_run, words

MIN_PRICE, MAX_PRICE = 100, 500  # $0.01 .. $0.05 (units of $0.0001)

_ORIGINAL_SIGNALS = re.compile(r"\b(our|we|log|recorded|survey|volunteers|field notes|data|table|measured)\b", re.I)


def heuristic_uniqueness(text: str, others: list[str]) -> tuple[int, str]:
    """No-LLM fallback: penalize overlap with other articles, reward original-data signals and numbers."""
    w = words(text)
    overlap = max((longest_common_run(w, words(o))[0] for o in others), default=0)
    overlap_penalty = min(60, overlap * 3)
    signals = len(_ORIGINAL_SIGNALS.findall(text))
    numbers = len(re.findall(r"\d+", text))
    score = max(0, min(100, 50 - overlap_penalty + signals * 6 + numbers * 3))
    reason = f"longest overlap with another article: {overlap} words; original-data signals: {signals}; numbers: {numbers}"
    return score, reason


def price_for(score: int) -> int:
    return MIN_PRICE + (MAX_PRICE - MIN_PRICE) * score // 100


async def suggest(text: str, others: list[str]) -> dict:
    data = await llm.generate_json(
        "You price content for AI agents. Rate how UNIQUE and VALUABLE this article is to an AI answering "
        "questions, from 0 (generic, freely available) to 100 (original data, hard to find elsewhere). "
        'Return JSON {"uniqueness": int, "reason": str}.\n\nARTICLE:\n' + text[:6000]
    )
    if data and isinstance(data.get("uniqueness"), int):
        score, reason, source = max(0, min(100, data["uniqueness"])), str(data.get("reason", ""))[:500], "llm"
    else:
        score, reason = heuristic_uniqueness(text, others)
        source = "heuristic"
    return {"uniqueness_score": score, "suggested_price": price_for(score), "reason": reason, "source": source}
